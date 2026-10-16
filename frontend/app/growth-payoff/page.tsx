import GrowthPayoff from "@/components/growth-payoff";
import data from "@/lib/growth-data.json";
export const metadata = {
  title: "Growth Payoff · QuantRAG",
  description:
    "Follow company investments from announcement to reported progress. Explore explicit investment-return assumptions.",
};
export default function Page() {
  return <GrowthPayoff report={data} />;
}
