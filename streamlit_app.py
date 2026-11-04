"""Start with: python -m streamlit run streamlit_app.py

This file is the interface. client.py handles HTTP; research.py holds plain Python logic.
The existing FastAPI application still owns retrieval, Gemini and numerical checks.
"""
import json
from pathlib import Path
from urllib.parse import urlparse

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from ui import client
from ui.presentation import (
    apply_design,
    chart_style,
    corpus_ring,
    coverage_grid,
    research_download,
    timeline,
)
from ui.research import note, project_payoff, read_notes

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
st.set_page_config(page_title='QuantRAG — Follow the evidence', layout='wide')


def load(name):
    return json.loads((ROOT / 'ui/data' / name).read_text())


def source_link(source):
    url = source.get('source_url', '')
    if isinstance(url, str) and urlparse(url).scheme == 'https':
        st.markdown('[Open source PDF](<' + url.replace('>', '%3E') + '>)')


def show_source(source, key):
    period = source.get('fiscal_label', source.get('period', ''))
    with st.expander(f"{source.get('symbol', '')} {period} · {source.get('speaker', 'Source')} · page {source.get('page', '?')}"):
        st.write(source.get('quote', source.get('text', '')))
        source_link(source)
        for neighbor in source.get('context', []):
            st.caption(neighbor['position'] + ' · ' + str(neighbor.get('speaker', '')) + ' · page ' + str(neighbor.get('page', '?')))
            st.write(neighbor['text'])
        if st.button('Save evidence', key=key):
            st.session_state.notes.append(note(f"{source.get('symbol', '')} {period}",
                                                source.get('quote', source.get('text', '')), [source]))
            st.success('Added to saved research for this session.')


def render_answer(result):
    if result.get('refused'):
        st.warning(result.get('refusal_reason', 'This question is outside the available coverage.'))
        return
    st.markdown(result.get('answer_markdown', ''))
    table = result.get('comparison_table', [])
    if table:
        rows = []
        for item in table:
            row = {'Metric': item['metric']}
            for cell in item['cells']:
                row[cell['company']] = cell['value'] + ' ' + ' '.join(f'[c{n}]' for n in cell['citations'])
            rows.append(row)
        st.dataframe(rows, hide_index=True)
    numbers = result.get('numbers', [])
    if numbers:
        with st.expander('Number checks — value matches, not a guarantee of correct attribution'):
            st.dataframe([{'Number': n.get('raw', n.get('text', '')), 'Status': n['status'],
                           'Detail': n.get('explanation', n.get('formula', 'Inspect the cited passage.'))}
                          for n in numbers], hide_index=True)
    hits = {h['chunk_id']: h for h in result.get('hits', [])}
    for citation in result.get('citations', []):
        source = dict(hits.get(citation['chunk_id'], {}), **citation)
        st.caption(f"Citation [c{citation['n']}]")
        show_source(source, f"answer-{citation['n']}")
    with st.expander('How this was answered'):
        st.json({'route': result.get('route'), 'timing_seconds': result.get('timing_s')})
        st.dataframe([{'company': h['symbol'], 'quarter': h['fiscal_label'], **h.get('scores', {})}
                      for h in result.get('hits', [])], hide_index=True)
    if st.button('Save answer'):
        st.session_state.notes.append(note(st.session_state.get('last_question', 'Analyst answer'),
                                            result.get('answer_markdown', ''), list(hits.values())))
        st.success('Saved for this session. Export from Saved research to keep a copy.')


def ask_page():
    st.title('Ask the analyst')
    st.caption('Official transcripts → retrieved evidence → cited answer → number checks')
    with st.form('question'):
        question = st.text_area('Your question', value=st.session_state.get('last_question', ''),
                                placeholder='What net interest margin did Kotak report in Q1 FY27?', max_chars=2000)
        submitted = st.form_submit_button('Ask the analyst', type='primary')
    retry = st.button('Retry last question', disabled=not st.session_state.get('last_question'))
    if submitted or retry:
        question = question.strip() if submitted else st.session_state.last_question
        if len(question) < 3:
            st.warning('Enter at least three characters.')
        else:
            st.session_state.last_question = question
            st.session_state.pop('answer', None)
            st.session_state.pop('ask_error', None)
            with st.status('Connecting to the analyst. An idle API may need time to wake…', expanded=True) as status:
                try:
                    st.session_state.answer = client.ask(question, on_status=st.write)
                    status.update(label='Answer received', state='complete', expanded=False)
                except client.AnalystError as exc:
                    st.session_state.ask_error = str(exc)
                    status.update(label='No live answer received', state='error')
    if st.session_state.get('ask_error'):
        st.error(st.session_state.ask_error)
        st.caption('These are previously saved real answers, not responses to your current question.')
        for item in load('saved-answers.json'):
            with st.expander(f"Example answer, saved {item['saved_at'][:10]} — {item['question']}"):
                st.markdown(item['answer_markdown'])
                for i, source in enumerate(item['sources']):
                    show_source(source, f"example-{item['id']}-{i}")
    if 'answer' in st.session_state:
        render_answer(st.session_state.answer)


def quarter_page(public):
    st.title('QuarterLens')
    st.caption('A closer look at what changed — with the source behind every signal.')
    companies = public['monitor']['companies']
    favorites = st.multiselect('Favourite companies (this session)', [c['symbol'] for c in companies],
                               key='favorites')
    selected = [c for c in companies if not favorites or c['symbol'] in favorites]
    company = st.selectbox('Company', selected, format_func=lambda c: c['name'])
    st.caption(f"Snapshot: {public['coverage']['as_of']} · Latest ingested quarter: {company['latest_period']}")
    facts = company.get('facts', [])
    if facts:
        basis = st.selectbox('Accounting basis — shown separately', sorted({f['basis'] for f in facts}))
        plotted = [f for f in facts if f['basis'] == basis]
        chart = alt.Chart(pd.DataFrame(plotted)).mark_point(size=130, color='#DDEB91', filled=True).encode(
            x=alt.X('period_end:T', title='Quarter ended'),
            y=alt.Y('value:Q', title=plotted[0].get('metric_label', 'Margin') + ' (%)', scale=alt.Scale(zero=False)),
            tooltip=['period:N', 'value:Q', 'basis:N'])
        st.altair_chart(chart_style(chart), width='stretch', theme=None)
        st.caption('Dots show sourced values on one basis. Missing values are not estimated; banks and IT margins are different metrics.')
        for i, fact in enumerate(plotted):
            show_source(dict(fact, symbol=company['symbol']), f"fact-{company['symbol']}-{i}")
    else:
        st.info('No reviewed margin figure is available. Browse the registered transcripts below.')
    for i, signal in enumerate(company.get('signals', [])):
        with st.expander(f"{signal.get('period', '')} · {signal.get('title', 'Reported change')}"):
            st.write(signal.get('summary', signal.get('detail', 'A reported change is a research prompt, not a verdict.')))
            for name in ['current', 'previous']:
                if isinstance(signal.get(name), dict):
                    show_source(dict(signal[name], symbol=company['symbol']), f'signal-{i}-{name}')
    with st.expander('Registered transcripts and management commentary'):
        coverage = next(c for c in public['coverage']['companies'] if c['symbol'] == company['symbol'])
        st.dataframe(coverage['documents'], hide_index=True)
        for i, item in enumerate(company.get('commentary', [])):
            show_source(dict(item, symbol=company['symbol']), f'commentary-{i}')
    for i, trail in enumerate(company.get('follow_through', [])):
        with st.expander('Follow-through · ' + trail['topic']):
            st.caption(trail['link_basis'] + ' · Needs review; no causal verdict.')
            for stage in ['before', 'after']:
                st.write(stage.capitalize())
                show_source(dict(trail[stage], symbol=company['symbol']), f'follow-{i}-{stage}')


def growth_page():
    st.title('Growth Payoff')
    report = load('growth-data.json')
    st.caption(f"Reviewed pilot · snapshot {report['as_of']} · sources, not investment-return verdicts")
    project = st.selectbox('Investment project', report['projects'], format_func=lambda p: p['symbol'] + ' · ' + p['name'])
    left, right = st.columns(2)
    left.metric(project['amount_label'], f"₹{project['amount']:,} crore" if project['amount'] is not None else 'Not extracted')
    right.metric('Financial payoff', project['payoff_status'])
    st.info(project['missing'])
    timeline(project['milestones'])
    st.dataframe([{'Quarter': m['period'], 'Stage': m['stage'], 'Milestone': m['label']}
                  for m in project['milestones']], hide_index=True)
    for i, milestone in enumerate(project['milestones']):
        show_source(dict(milestone, symbol=project['symbol']), f"milestone-{project['id']}-{i}")
    if project.get('amount_source'):
        show_source(dict(project['amount_source'], symbol=project['symbol']), 'investment-amount')
    metric = project.get('operating_metric')
    if metric:
        st.subheader(metric['label'])
        st.bar_chart(pd.DataFrame({'Stage': [metric['before_label'], metric['after_label']],
                                    metric['unit']: [metric['before'], metric['after']]}).set_index('Stage'))
        st.caption('The later figure is a lower bound. Distribution growth does not establish profit or ROI.')
    st.subheader('Explore your assumptions')
    st.warning('Sensitivity calculation, not a forecast. No share-price prediction, compounding or cash-flow conversion.')
    a, b = st.columns(2)
    capital = a.number_input('Assumed investment (₹ crore)', min_value=1.0, max_value=1e7,
                              value=float(project['amount'] or 100), key='capital-' + project['id'])
    annual_return = b.slider('Assumed annual operating return (%)', -20, 50, 10)
    ramp = a.slider('Years to reach full operating contribution', 1, 5, 2)
    start = b.slider('First operating year', 1, 5, 1)
    years = st.radio('Scenario horizon', [3, 5], horizontal=True)
    data = project_payoff(capital, annual_return, ramp, start, years)
    values = [r['Annual incremental operating profit (₹ crore)'] for r in data]
    lower, upper = min(0, min(values)), max(0, max(values))
    padding = max((upper - lower) * .1, 1)
    chart = alt.Chart(pd.DataFrame(data)).mark_line(point=True, strokeDash=[6, 4], color='#DDEB91').encode(
        x=alt.X('Year:O'), y=alt.Y('Annual incremental operating profit (₹ crore):Q',
            scale=alt.Scale(domain=[lower, upper + padding], nice=True), axis=alt.Axis(tickCount=5)))
    st.altair_chart(chart_style(chart), width='stretch', theme=None)
    with st.expander('The complete calculation'):
        st.code('annual_profit = capital * annual_return / 100\n'
                'ramp_fraction = min(1, max(0, (year - start_year + 1) / ramp_years))\n'
                'profit_for_year = annual_profit * ramp_fraction', language='python')
        st.dataframe(data, hide_index=True)


def research_page(public):
    st.title('Saved research')
    st.caption('Private to this Streamlit session. Export before closing; no accounts, database history or cross-device sync.')
    with st.expander('Check a research idea against covered quarters'):
        companies = [c for c in public['coverage']['companies'] if c['documents']]
        company = st.selectbox('Company to check', companies, format_func=lambda c: c['name'])
        thesis = st.text_area('Your research idea', max_chars=2000)
        periods = st.multiselect('Up to four available quarters', [d['fiscal_label'] for d in company['documents']], max_selections=4)
        if st.button('Find source-backed suggestions'):
            if len(thesis.strip()) < 3 or not periods:
                st.warning('Enter an idea and choose at least one covered quarter.')
            else:
                try:
                    with st.spinner('Reviewing retrieved evidence…'):
                        st.session_state.suggestions = client.check_research(company['symbol'], thesis.strip(), periods)
                except client.AnalystError as exc:
                    st.error(str(exc))
        result = st.session_state.get('suggestions')
        if result:
            st.caption(result['symbol'] + ' · ' + result['thesis'] + ' · Suggestions require your review.')
            for i, suggestion in enumerate(result['suggestions']):
                st.write(suggestion['period'] + ' · ' + suggestion['relation'])
                st.write(suggestion['reason'])
                for j, source in enumerate(suggestion['evidence']):
                    show_source(source, f'idea-{i}-{j}')
    if not st.session_state.notes:
        st.info('Your workspace is empty. Save a cited answer or a source passage to begin.')
    with st.form('new_note'):
        title = st.text_input('Research question / title', max_chars=200)
        text = st.text_area('Your note', max_chars=10000)
        if st.form_submit_button('Add note'):
            if title.strip() and text.strip():
                st.session_state.notes.append(note(title.strip(), text.strip()))
                st.rerun()
            else:
                st.warning('Enter a title and a note.')
    for saved in st.session_state.notes:
        saved['assessment'] = st.session_state.get('assessment-' + saved['id'], saved['assessment'])
    research_download(st.session_state.notes)
    with st.expander('Import a backup'):
        uploaded = st.file_uploader('Import a Streamlit research export (replaces session notes)', type=['json'])
        pasted = st.text_area('Or paste a research JSON export', max_chars=2000000,
                              help='Works even when a serverless file upload cannot reconnect to its session.')
        if st.button('Import notes', disabled=uploaded is None and not pasted.strip()):
            try:
                st.session_state.notes = read_notes(uploaded.getvalue() if uploaded else pasted.encode('utf-8'))
                st.rerun()
            except (ValueError, TypeError, UnicodeError):
                st.error('Invalid export. Import a JSON file exported by this Streamlit app, under 2 MB.')
    for item in list(st.session_state.notes):
        with st.expander(item['title']):
            st.caption('Saved ' + item['saved_at'])
            st.write(item['text'])
            item['assessment'] = st.selectbox('Your assessment', ['Unresolved', 'Supporting', 'Challenging'],
                index=['Unresolved', 'Supporting', 'Challenging'].index(item['assessment']), key='assessment-' + item['id'])
            for source in item['sources']:
                source_link(source)
            if st.button('Delete note', key='delete-' + item['id']):
                st.session_state.notes.remove(item)
                st.rerun()


def evaluation_page(public):
    st.title('Evaluation')
    st.warning('Development set, not a final benchmark. Human-reviewed gold evaluation and blind numeric labels remain pending.')
    report = load('development-results.json')
    st.caption(f"Recorded on {report['machine']} · commit {report['source_commit']} · source: {report['source']}")
    st.dataframe(report['retrieval'], hide_index=True)
    st.bar_chart(pd.DataFrame(report['retrieval']).set_index('name')[['hits_min', 'hits_max']])
    st.subheader('Recorded reranker memory (MB)')
    st.dataframe([report['memory']], hide_index=True)
    st.link_button('CI runs on main — current test count and coverage',
                   'https://github.com/aaranarc/earnings-call-analyst/actions/workflows/ci.yml?query=branch%3Amain')
    with st.expander('Published evaluation payload'):
        st.json(public['evaluation'])


def go_to(page):
    st.session_state.navigation = page


def home_page(public):
    title, action = st.columns([4, 1], vertical_alignment='center')
    title.title('Follow the claim. Check the number.')
    title.caption('Your company research, connected to the original evidence.')
    action.button('Ask the analyst', type='primary', on_click=go_to, args=('Ask the analyst',), width='stretch')
    covered = [c for c in public['coverage']['companies'] if c['documents']]
    projects = load('growth-data.json')['projects']
    metrics = [('Covered companies', len(covered)),
               ('Official transcripts', sum(len(c['documents']) for c in covered)),
               ('Investment projects', len(projects)), ('Saved findings', len(st.session_state.notes))]
    for column, (label, value) in zip(st.columns(4), metrics, strict=True):
        column.metric(label, f'{value:02d}')
    st.write('')
    library, sectors = st.columns([1.75, 1])
    with library.container(border=True):
        st.subheader('Inside the library')
        st.caption('Available quarters · select QuarterLens to inspect a company')
        coverage_grid(covered)
        st.caption('Snapshot · ' + public['coverage']['as_of'] + ' · Missing quarters stay visible.')
    with sectors.container(border=True):
        st.subheader('Research coverage')
        st.caption('Transcripts by sector')
        corpus_ring(covered)
        st.caption('Partial, dated source coverage. Not a live market feed.')
    st.write('')
    left, right = st.columns([1.75, 1])
    with left.container(border=True):
        heading, control = st.columns([3, 1])
        heading.subheader('Changes worth a closer look')
        control.button('QuarterLens →', on_click=go_to, args=('QuarterLens',), width='stretch')
        signals = [(company, signal) for company in public['monitor']['companies'] for signal in company.get('signals', [])]
        signals.sort(key=lambda pair: (int(pair[1]['period'][-2:]), int(pair[1]['period'][1])), reverse=True)
        if not signals:
            st.info('No reviewed change signals in this snapshot.')
        for company, signal in signals[:4]:
            label, value = st.columns([4, 1])
            label.write('**' + company['symbol'] + ' · ' + signal.get('title', 'Reported change') + '**')
            label.caption(signal['period'] + ' · Management-reported; review the source')
            delta = signal.get('change_bps')
            value.write(f'{delta:+g} bps' if isinstance(delta, (int, float)) else 'Review')
        st.caption('These are research prompts, not company ratings or buy/sell recommendations.')
    with right.container(border=True):
        st.subheader('Growth Payoff')
        st.caption('Investment → execution → financial evidence')
        for project in projects[:3]:
            st.write('**' + project['symbol'] + ' · ' + project['name'] + '**')
            st.caption(project['outcome'])
        st.button('Explore projects →', on_click=go_to, args=('Growth Payoff',), width='stretch')
    research, evaluation = st.columns(2)
    with research.container(border=True):
        st.subheader('Your evidence pile')
        st.caption('Starts empty. Save what you find; keep control of your assessment.')
        st.button('Open saved research →', on_click=go_to, args=('Saved research',))
    with evaluation.container(border=True):
        st.subheader('Show the work')
        st.caption('Development results are available. Final human-reviewed evaluation is pending.')
        st.button('Inspect evaluation →', on_click=go_to, args=('Evaluation',))


def main():
    apply_design()
    st.session_state.setdefault('notes', [])
    pages = {'ask': 'Ask the analyst', 'watchlist': 'QuarterLens', 'growth-payoff': 'Growth Payoff',
             'research': 'Saved research', 'eval': 'Evaluation', 'how-it-works': 'How it works'}
    st.session_state.setdefault('navigation', pages.get(st.query_params.get('page'), 'Home'))
    if 'last_question' not in st.session_state and st.query_params.get('q'):
        st.session_state.last_question = str(st.query_params['q'])[:2000]
    public = load('public-data.json')
    st.sidebar.title('QuantRAG')
    st.sidebar.caption('Follow the evidence.')
    st.sidebar.divider()
    page = st.sidebar.radio('Navigate', ['Home', 'Ask the analyst', 'QuarterLens', 'Growth Payoff', 'Saved research', 'Evaluation', 'How it works'], key='navigation')
    st.sidebar.divider()
    st.sidebar.caption('Your research. Your assessment.')
    if st.sidebar.button('Check API connection'):
        status = client.health()
        st.sidebar.write('API reachable' if status['status'] == 'ok' else 'Start the API or wait for it to wake.')
        if status['status'] == 'ok' and not status.get('configured'):
            st.sidebar.warning('API needs database and Gemini configuration.')
    if page == 'Ask the analyst':
        ask_page()
    elif page == 'QuarterLens':
        quarter_page(public)
    elif page == 'Growth Payoff':
        growth_page()
    elif page == 'Saved research':
        research_page(public)
    elif page == 'Evaluation':
        evaluation_page(public)
    elif page == 'How it works':
        st.title('How it works')
        st.code('Official PDFs → parse → chunks + embeddings → PostgreSQL\n'
                'Question → Streamlit → FastAPI → hybrid search → reranker\n'
                '         → Gemini → citation + number checks → Streamlit')
        st.write('The dashboard is Python. FastAPI owns the research pipeline. PostgreSQL stores source passages; '
                 'Gemini writes answers from retrieved context. A matching number can still have the wrong attribution.')
        st.caption('See docs/LEARNING.md for the file-by-file explanation.')
    else:
        home_page(public)
    st.caption('Research software. Sources and generated answers require review; scenarios are assumptions.')


if __name__ == '__main__':
    main()
