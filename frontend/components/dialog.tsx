"use client";
import { useEffect, useRef } from "react";
import { X } from "lucide-react";
export default function Dialog({
  title,
  onClose,
  children,
  drawer = false,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  drawer?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    const before = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = before;
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={drawer ? "dialog drawer" : "dialog"}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      aria-label={title}
    >
      <header className="dialog-head">
        <h2>{title}</h2>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close dialog"
        >
          <X size={21} />
        </button>
      </header>
      {children}
    </dialog>
  );
}
