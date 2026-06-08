import { memo, useState } from "react";
import type { FormEvent } from "react";
import type { EventFormData, EventPriority, EventTone, ScheduleEvent } from "./types";
import WheelPicker, { type WheelItem } from "./WheelPicker";
import { TONE_COLORS, TONE_LABELS } from "./scheduleUtils";

type EventModalProps = {
  editingEvent: ScheduleEvent | null;
  currentMonth: number;
  currentYear: number;
  onSubmit: (data: EventFormData) => void;
  onClose: () => void;
};

// 月份
const MONTHS: WheelItem[] = Array.from({ length: 12 }, (_, i) => ({
  value: i + 1,
  label: `${i + 1} 月`,
}));

// 1–31 天
const DAYS: WheelItem[] = Array.from({ length: 31 }, (_, i) => ({
  value: i + 1,
  label: `${i + 1} 日`,
}));

// 小時 00–23
const HOURS: WheelItem[] = Array.from({ length: 24 }, (_, i) => ({
  value: i,
  label: `${String(i).padStart(2, "0")}`,
}));

// 分鐘 00, 05, 10, ... 55
const MINUTES: WheelItem[] = Array.from({ length: 12 }, (_, i) => ({
  value: i * 5,
  label: String(i * 5).padStart(2, "0"),
}));

// Tone 滾輪
const TONES: WheelItem[] = (["IP4", "IP3", "IP2", "IP1"] as EventTone[]).map((t) => ({
  value: t,
  label: `${t} · ${TONE_LABELS[t]}`,
}));

// Priority 滾輪
const PRIORITIES: WheelItem[] = (["low", "medium", "high"] as EventPriority[]).map((p) => ({
  value: p,
  label: p === "low" ? "低" : p === "medium" ? "中" : "高",
}));

const EventModal = memo(function EventModal({
  editingEvent,
  currentMonth,
  currentYear,
  onSubmit,
  onClose,
}: EventModalProps) {
  const today = new Date();

  const [title, setTitle] = useState(editingEvent?.title ?? "");
  const [month, setMonth] = useState(editingEvent?.month ?? currentMonth);
  const [day, setDay] = useState(editingEvent?.date ?? today.getDate());

  const parseTime = (t: string | undefined) => {
    if (!t) return { hour: 9, minute: 0 };
    const [h, m] = t.split(":").map(Number);
    return { hour: h ?? 9, minute: m ?? 0 };
  };
  const [startHour, setStartHour] = useState(
    editingEvent?.startTime ? parseTime(editingEvent.startTime).hour : 9
  );
  const [startMinute, setStartMinute] = useState(
    editingEvent?.startTime ? parseTime(editingEvent.startTime).minute : 0
  );
  const [endHour, setEndHour] = useState(
    editingEvent?.endTime ? parseTime(editingEvent.endTime).hour : 10
  );
  const [endMinute, setEndMinute] = useState(
    editingEvent?.endTime ? parseTime(editingEvent.endTime).minute : 0
  );

  const [location, setLocation] = useState(editingEvent?.location ?? "");
  const [description, setDescription] = useState(editingEvent?.description ?? "");
  const [tone, setTone] = useState<EventTone>(editingEvent?.tone ?? "IP4");
  const [priority, setPriority] = useState<EventPriority>(editingEvent?.priority ?? "medium");

  const maxDay = new Date(currentYear, currentMonth, 0).getDate();
  const safeDay = Math.min(day, maxDay);

  const fmt = (h: number, m: number) =>
    `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return;
    onSubmit({
      title: title.trim(),
      date: safeDay,
      month,
      year: currentYear,
      startTime: fmt(startHour, startMinute),
      endTime: fmt(endHour, endMinute),
      location: location || undefined,
      description: description || undefined,
      tone,
      priority,
      id: editingEvent?.id,
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content evo-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="evo-modal-header">
          <div className="evo-modal-dot" style={{ background: TONE_COLORS[tone] }} />
          <h2>{editingEvent ? "編輯行程" : "新增行程"}</h2>
          <button className="evo-close-btn" onClick={onClose} aria-label="關閉">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="evo-form">
          {/* 標題 */}
          <div className="evo-section evo-section--title">
            <input
              className="evo-title-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="行程標題"
              required
              autoFocus
            />
          </div>

          {/* 日期 / 時間 並排 */}
          <div className="evo-row">
            {/* 日期 */}
            <div className="evo-group">
              <span className="evo-group-label">日期</span>
              <div className="evo-date-wheels">
                <WheelPicker items={MONTHS} value={month} onChange={(v) => {
                  setMonth(v as number);
                  const newMax = new Date(currentYear, v as number, 0).getDate();
                  if (day > newMax) setDay(newMax);
                }} />
                <WheelPicker items={DAYS.slice(0, maxDay)} value={safeDay} onChange={(v) => setDay(v as number)} />
              </div>
            </div>

            {/* 時間 */}
            <div className="evo-group">
              <span className="evo-group-label">時間</span>
              <div className="evo-time-wheels">
                <div className="evo-time-block">
                  <span className="evo-time-tag">開始</span>
                  <div className="evo-time-pair">
                    <WheelPicker items={HOURS} value={startHour} onChange={(v) => setStartHour(v as number)} />
                    <span className="evo-time-colon">:</span>
                    <WheelPicker items={MINUTES} value={startMinute} onChange={(v) => setStartMinute(v as number)} />
                  </div>
                </div>
                <div className="evo-time-block">
                  <span className="evo-time-tag">結束</span>
                  <div className="evo-time-pair">
                    <WheelPicker items={HOURS} value={endHour} onChange={(v) => setEndHour(v as number)} />
                    <span className="evo-time-colon">:</span>
                    <WheelPicker items={MINUTES} value={endMinute} onChange={(v) => setEndMinute(v as number)} />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 地點 + 說明 */}
          <div className="evo-inputs-row">
            <div className="evo-input-wrap">
              <span className="evo-input-label">地點</span>
              <input
                className="evo-text-input"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="新增地點"
              />
            </div>
            <div className="evo-input-wrap evo-input-wrap--grow">
              <span className="evo-input-label">說明</span>
              <textarea
                className="evo-text-input evo-textarea"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="備註..."
                rows={2}
              />
            </div>
          </div>

          {/* 底部屬性列 */}
          <div className="evo-props-row">
            <div className="evo-prop-group">
              <span className="evo-prop-label">顏色</span>
              <div className="evo-tone-row">
                <div className="evo-tone-swatch" style={{ background: TONE_COLORS[tone] }} />
                <WheelPicker
                  items={TONES}
                  value={tone}
                  onChange={(v) => setTone(v as EventTone)}
                />
              </div>
            </div>
            <div className="evo-prop-group">
              <span className="evo-prop-label">優先度</span>
              <WheelPicker
                items={PRIORITIES}
                value={priority}
                onChange={(v) => setPriority(v as EventPriority)}
              />
            </div>
          </div>

          {/* 按鈕 */}
          <div className="evo-actions">
            <button type="button" className="evo-btn evo-btn--cancel" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="evo-btn evo-btn--submit">
              {editingEvent ? "儲存修改" : "新增行程"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
});

export default EventModal;