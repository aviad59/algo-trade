import {
  createContext, useCallback, useContext, useRef, useState, type ReactNode,
} from "react";
import { createPortal } from "react-dom";

interface TipState {
  content: ReactNode;
  x: number;
  y: number;
}

interface TooltipApi {
  show: (content: ReactNode, x: number, y: number) => void;
  hide: () => void;
}

const TooltipContext = createContext<TooltipApi | null>(null);

export function useTooltip(): TooltipApi {
  const ctx = useContext(TooltipContext);
  if (!ctx) throw new Error("useTooltip must be used within <TooltipProvider>");
  return ctx;
}

export function TooltipProvider({ children }: { children: ReactNode }) {
  const [tip, setTip] = useState<TipState | null>(null);
  const boxRef = useRef<HTMLDivElement | null>(null);

  const show = useCallback((content: ReactNode, x: number, y: number) => {
    setTip({ content, x, y });
  }, []);
  const hide = useCallback(() => setTip(null), []);

  // Position after render so we can measure and flip near edges.
  let style: React.CSSProperties = { left: -9999, top: -9999 };
  if (tip) {
    const box = boxRef.current;
    const w = box?.offsetWidth ?? 200;
    const h = box?.offsetHeight ?? 60;
    let left = tip.x + 14;
    let top = tip.y + 14;
    if (left + w > window.innerWidth - 8) left = tip.x - w - 14;
    if (top + h > window.innerHeight - 8) top = tip.y - h - 14;
    style = { left, top };
  }

  return (
    <TooltipContext.Provider value={{ show, hide }}>
      {children}
      {tip &&
        createPortal(
          <div className="tooltip" ref={boxRef} role="status" style={style}>
            {tip.content}
          </div>,
          document.body,
        )}
    </TooltipContext.Provider>
  );
}
