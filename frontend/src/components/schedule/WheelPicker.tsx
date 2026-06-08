import { memo, useCallback, useEffect, useRef, useState } from "react";

export type WheelItem = { value: string | number; label: string };

type WheelPickerProps = {
  items: WheelItem[];
  value: string | number;
  onChange: (value: string | number) => void;
  label?: string;
  /** 滾輪可見列數，預設 5 */
  visibleRows?: number;
};

const WheelPicker = memo(function WheelPicker({
  items,
  value,
  onChange,
  label,
  visibleRows = 3,
}: WheelPickerProps) {
  const itemHeight = 36;
  const containerHeight = itemHeight * visibleRows;
  const selectedIndex = items.findIndex((i) => i.value === value);

  const [scrollTop, setScrollTop] = useState(() => {
    const idx = items.findIndex((i) => i.value === value);
    return idx >= 0 ? idx * itemHeight : 0;
  });

  const wrapperRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);
  const startY = useRef(0);
  const startScrollTop = useRef(0);
  const velocity = useRef(0);
  const lastY = useRef(0);
  const lastTime = useRef(0);
  const rafId = useRef<number>(0);

  // 同步外部 value 變化
  useEffect(() => {
    const idx = items.findIndex((i) => i.value === value);
    if (idx >= 0) {
      setScrollTop(idx * itemHeight);
    }
  }, [value, items]);

  const clamp = (v: number) => Math.max(0, Math.min(v, (items.length - 1) * itemHeight));

  const settleAtItem = useCallback(
    (top: number) => {
      const idx = Math.round(top / itemHeight);
      const clamped = Math.max(0, Math.min(idx, items.length - 1));
      setScrollTop(clamped * itemHeight);
      onChange(items[clamped].value);
    },
    [items, itemHeight, onChange]
  );

  // 彈性滾動 + 吸附
  const onPointerDown = (e: React.PointerEvent) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    isDragging.current = true;
    startY.current = e.clientY;
    startScrollTop.current = scrollTop;
    lastY.current = e.clientY;
    lastTime.current = Date.now();
    velocity.current = 0;
    if (rafId.current) cancelAnimationFrame(rafId.current);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!isDragging.current) return;
    const dy = e.clientY - startY.current;
    const newTop = clamp(startScrollTop.current - dy);
    setScrollTop(newTop);
    velocity.current = (e.clientY - lastY.current) / (Date.now() - lastTime.current + 1);
    lastY.current = e.clientY;
    lastTime.current = Date.now();
  };

  const onPointerUp = (e: React.PointerEvent) => {
    if (!isDragging.current) return;
    isDragging.current = false;
    e.currentTarget.releasePointerCapture(e.pointerId);

    // 慣性
    const fling = velocity.current * 120;
    const targetTop = clamp(scrollTop + fling);

    // 動畫到最近 item
    const idx = Math.round(targetTop / itemHeight);
    const clamped = Math.max(0, Math.min(idx, items.length - 1));
    setScrollTop(clamped * itemHeight);
    onChange(items[clamped].value);
  };

  // 滑鼠滾輪支援
  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 1 : -1;
    const currentIdx = items.findIndex((i) => i.value === value);
    const nextIdx = Math.max(0, Math.min(currentIdx + delta, items.length - 1));
    const newTop = nextIdx * itemHeight;
    setScrollTop(newTop);
    onChange(items[nextIdx].value);
  };

  const halfRows = Math.floor(visibleRows / 2);
  const paddingTop = itemHeight * halfRows;

  return (
    <div className="wheel-picker-wrapper">
      {label && <span className="wheel-picker-label">{label}</span>}
      <div
        ref={wrapperRef}
        className="wheel-picker-container"
        style={{ height: containerHeight }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onWheel={onWheel}
      >
        {/* 上方遮罩 */}
        <div
          className="wheel-picker-mask wheel-picker-mask-top"
          style={{ height: paddingTop, marginTop: -paddingTop }}
        />
        {/* 下方的遮罩 */}
        <div
          className="wheel-picker-mask wheel-picker-mask-bottom"
          style={{ height: paddingTop }}
        />
        {/* 選中指示線 */}
        <div
          className="wheel-picker-indicator"
          style={{ top: paddingTop, height: itemHeight }}
        />
        {/* 滾輪內容 */}
        <div
          className="wheel-picker-scroll"
          style={{
            transform: `translateY(${-scrollTop}px)`,
            paddingTop,
          }}
        >
          {items.map((item) => (
            <div
              key={item.value}
              className={`wheel-picker-item${item.value === value ? " selected" : ""}`}
              style={{ height: itemHeight, lineHeight: `${itemHeight}px` }}
            >
              {item.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
});

export default WheelPicker;