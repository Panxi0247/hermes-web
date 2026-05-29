import { useState, useMemo, useEffect, memo } from "react";
import "./Schedule.css";

// ============================================================
// 常數與工具函式（module-level, no React state）
// ============================================================
type EventTone = "IP1" | "IP2" | "IP3" | "IP4";
type EventPriority = "low" | "medium" | "high";
type Participant = { id: string; name: string };
type ScheduleEvent = {
  id: string;
  title: string;
  date: number;
  month: number;
  year: number;
  startTime?: string;
  endTime?: string;
  location?: string;
  description?: string;
  tone: EventTone;
  priority?: EventPriority;
  participants: Participant[];
};

type ScheduleView = "agenda" | "calendar";

const generateId = () => Math.random().toString(36).slice(2, 10);
const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const TONE_COLORS: Record<EventTone, string> = {
  IP4: "var(--IP4, #fce24e)",
  IP3: "var(--IP3, #2dcc17)",
  IP2: "var(--IP2, #20f0e5)",
  IP1: "var(--IP1, #3b74ca)",
};

const calcDuration = (start: string, end: string) => {
  const [sh, sm] = start.split(":").map(Number);
  const [eh, em] = end.split(":").map(Number);
  const mins = eh * 60 + em - (sh * 60 + sm);
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `${h} hr ${m} min` : `${h} hr`;
};

// ============================================================
// EventModal Props & Component（module-level）
// ============================================================
type EventModalProps = {
  editingEvent: ScheduleEvent | null;
  currentMonth: number;
  currentYear: number;
  onSubmit: (data: Omit<ScheduleEvent, "id" | "participants"> & { id?: string }) => void;
  onClose: () => void;
};

const EventModal = memo(function EventModal({
  editingEvent,
  currentMonth,
  currentYear,
  onSubmit,
  onClose,
}: EventModalProps) {
  const today = new Date();
  const [title, setTitle] = useState(editingEvent?.title ?? "");
  const [date, setDate] = useState(editingEvent?.date ?? today.getDate());
  const [startTime, setStartTime] = useState(editingEvent?.startTime ?? "");
  const [endTime, setEndTime] = useState(editingEvent?.endTime ?? "");
  const [location, setLocation] = useState(editingEvent?.location ?? "");
  const [description, setDescription] = useState(editingEvent?.description ?? "");
  const [tone, setTone] = useState<EventTone>(editingEvent?.tone ?? "IP4");
  const [priority, setPriority] = useState<EventPriority>(editingEvent?.priority ?? "medium");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    const eventData = {
      title: title.trim(),
      date,
      month: currentMonth,
      year: currentYear,
      startTime: startTime || undefined,
      endTime: endTime || undefined,
      location: location || undefined,
      description: description || undefined,
      tone,
      priority,
      id: editingEvent?.id,
    };
    onSubmit(eventData);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>{editingEvent ? "Edit Event" : "New Event"}</h2>
        <form onSubmit={handleSubmit} className="event-form">
          <label>Title * <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Event title" required autoFocus /></label>
          <label>Date * <input type="number" min={1} max={31} value={date} onChange={(e) => setDate(Number(e.target.value))} required /></label>
          <div className="form-row">
            <label>Start <input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} /></label>
            <label>End <input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} /></label>
          </div>
          <label>Location <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Location..." /></label>
          <label>Description <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Details..." rows={3} /></label>
          <div className="form-row">
            <label>Tone
              <select value={tone} onChange={(e) => setTone(e.target.value as EventTone)}>
                <option value="IP4">IP4</option><option value="IP3">IP3</option>
                <option value="IP2">IP2</option><option value="IP1">IP1</option>
              </select>
            </label>
            <label>Priority
              <select value={priority} onChange={(e) => setPriority(e.target.value as EventPriority)}>
                <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option>
              </select>
            </label>
          </div>
          <div className="form-actions">
            <button type="button" className="btn-cancel" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-submit">{editingEvent ? "Save" : "Add Event"}</button>
          </div>
        </form>
      </div>
    </div>
  );
});

// ============================================================
// DetailPanel Props & Component（module-level）
// ============================================================
type DetailPanelProps = {
  selectedEvent: ScheduleEvent | null;
  onEdit: (event: ScheduleEvent) => void;
  onDelete: (id: string) => void;
};

const DetailPanel = memo(function DetailPanel({ selectedEvent, onEdit, onDelete }: DetailPanelProps) {
  if (!selectedEvent) {
    return <div className="detail-card empty-panel"><p>Select an event to view details</p></div>;
  }

  const dayOfWeek = new Date(selectedEvent.year, selectedEvent.month - 1, selectedEvent.date)
    .toLocaleString("en-US", { weekday: "short" });
  const eventMonthName = new Date(selectedEvent.year, selectedEvent.month - 1, 1)
    .toLocaleString("en-US", { month: "short" });

  return (
    <>
      <div className="featured-event" style={{ borderLeftColor: TONE_COLORS[selectedEvent.tone] }}>
        <span>
          {selectedEvent.priority === "high" ? "★ High Priority"
            : selectedEvent.priority === "low" ? "○ Low Priority"
            : "● Medium Priority"}
        </span>
        <h3>{selectedEvent.title}</h3>
        <p>
          {selectedEvent.startTime
            ? `${selectedEvent.startTime}${selectedEvent.endTime ? ` - ${selectedEvent.endTime}` : ""}`
            : "All day"}
        </p>
      </div>

      <div className="detail-card">
        <h3>行程摘要</h3>
        <dl>
          <div><dt>日期</dt><dd>{dayOfWeek}, {eventMonthName} {selectedEvent.date}, {selectedEvent.year}</dd></div>
          {selectedEvent.location && <div><dt>地點</dt><dd>{selectedEvent.location}</dd></div>}
          {selectedEvent.startTime && selectedEvent.endTime && <div><dt>時長</dt><dd>{calcDuration(selectedEvent.startTime, selectedEvent.endTime)}</dd></div>}
          {selectedEvent.description && <div><dt>說明</dt><dd>{selectedEvent.description}</dd></div>}
        </dl>
        <div className="detail-actions">
          <button className="btn-edit" onClick={() => onEdit(selectedEvent)}>Edit</button>
          <button className="btn-delete" onClick={() => { if (confirm(`Delete "${selectedEvent.title}"?`)) onDelete(selectedEvent.id); }}>Delete</button>
        </div>
      </div>
    </>
  );
});

// ============================================================
// Schedule 主元件
// ============================================================
const defaultEvents: ScheduleEvent[] = [];

export default function Schedule() {
  const [view, setView] = useState<ScheduleView>("calendar");
  const [events, setEvents] = useState<ScheduleEvent[]>(() => {
    const saved = localStorage.getItem("hermes-schedule-events");
    return saved ? JSON.parse(saved) : defaultEvents;
  });
  const [searchQuery, setSearchQuery] = useState("");
  const [currentDate, setCurrentDate] = useState(() => new Date());
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<ScheduleEvent | null>(null);

  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth() + 1;

  const filteredEvents = useMemo(() => {
    if (!searchQuery.trim()) return events;
    const q = searchQuery.toLowerCase();
    return events.filter(
      (e) =>
        e.title.toLowerCase().includes(q) ||
        (e.location?.toLowerCase().includes(q) ?? false)
    );
  }, [events, searchQuery]);

  const selectedEvent = useMemo(
    () => events.find((e) => e.id === selectedEventId) ?? null,
    [events, selectedEventId]
  );

  // localStorage 持久化
  useEffect(() => {
    localStorage.setItem("hermes-schedule-events", JSON.stringify(events));
  }, [events]);

  const addEvent = (data: Omit<ScheduleEvent, "id" | "participants">) => {
    setEvents((prev) => [...prev, { ...data, id: generateId(), participants: [] }]);
  };

  const updateEvent = (id: string, data: Partial<ScheduleEvent>) => {
    setEvents((prev) => prev.map((e) => (e.id === id ? { ...e, ...data } : e)));
  };

  const deleteEvent = (id: string) => {
    setEvents((prev) => prev.filter((e) => e.id !== id));
    setSelectedEventId((prev) => (prev === id ? null : prev));
  };

  // eventTone: 依 priority 給 default tone
  const eventTone = (priority: EventPriority = "medium"): EventTone => {
    if (priority === "high") return "IP4";
    if (priority === "low") return "IP1";
    return "IP2";
  };

  const prevMonth = () => setCurrentDate(new Date(currentYear, currentDate.getMonth() - 1, 1));
  const nextMonth = () => setCurrentDate(new Date(currentYear, currentDate.getMonth() + 1, 1));

  // ── 月曆格資料 ──
  const daysInMonth = new Date(currentYear, currentMonth, 0).getDate();
  const firstDayOfWeek = new Date(currentYear, currentMonth - 1, 1).getDay();
  const calendarDays: (number | null)[] = [
    ...Array(firstDayOfWeek).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  // eventsForDay: (day: number) => ScheduleEvent[]
  const eventsForDay = (day: number) =>
    filteredEvents.filter((e) => e.date === day && e.month === currentMonth && e.year === currentYear);

  const isToday = (day: number) => {
    const t = new Date();
    return day === t.getDate() && currentMonth === t.getMonth() + 1 && currentYear === t.getFullYear();
  };

  // ── 渲染 ──
  return (
    <div className="schedule">
      <section className="schedule-main">
        <div className="schedule-toolbar">
          <div>
            <p className="eyebrow">Schedule</p>
            <h2>行程中心</h2>
          </div>
          <div className="schedule-actions">
            <label className="schedule-search">
              <span>Search</span>
              <input placeholder="搜尋事件或活動" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
            </label>
            <button className="schedule-add" onClick={() => { setEditingEvent(null); setIsModalOpen(true); }}>+ Add</button>
          </div>
        </div>

        <div className="schedule-controls">
          <div className="view-switch">
            <button className={view === "calendar" ? "active" : ""} onClick={() => setView("calendar")}>月</button>
            <button className={view === "agenda" ? "active" : ""} onClick={() => setView("agenda")}>列表</button>
          </div>
          <div className="month-control">
            <button onClick={prevMonth}>‹</button>
            <strong>{currentYear} / {currentMonth.toString().padStart(2, "0")}</strong>
            <button onClick={nextMonth}>›</button>
          </div>
        </div>

        {view === "calendar" ? (
          <div className="calendar-card">
            <div className="calendar-weekdays">
              {weekdays.map((d) => <div key={d}>{d}</div>)}
            </div>
            <div className="calendar-grid">
              {calendarDays.map((day, idx) =>
                day ? (
                  <div
                    key={idx}
                    className={`calendar-cell${isToday(day) ? " today" : ""}`}
                    onClick={() => {
                      const evs = eventsForDay(day);
                      setSelectedEventId(evs[0]?.id ?? null);
                    }}
                  >
                    <div className="day-number">{day}</div>
                    <div className="day-events">
                      {eventsForDay(day).slice(0, 3).map((ev) => (
                        <div
                          key={ev.id}
                          className={`mini-event ${ev.tone}`}
                          onClick={(e) => { e.stopPropagation(); setSelectedEventId(ev.id); }}
                        >
                          <strong>{ev.title}</strong>
                          {ev.startTime && <span>{ev.startTime}</span>}
                        </div>
                      ))}
                      {eventsForDay(day).length > 3 && (
                        <div className="more-events">+{eventsForDay(day).length - 3}</div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div key={idx} className="calendar-cell muted" />
                )
              )}
            </div>
          </div>
        ) : (
          <div className="agenda-list">
            {filteredEvents.length === 0 && <div className="empty-state">尚無行程</div>}
            {filteredEvents.map((ev) => (
              <div
                key={ev.id}
                className={`agenda-item ${ev.tone}${selectedEventId === ev.id ? " selected" : ""}`}
                onClick={() => setSelectedEventId(ev.id)}
              >
                <div className="agenda-date">
                  <span>{new Date(ev.year, ev.month - 1, ev.date).toLocaleString("en-US", { weekday: "short" })}</span>
                  <strong>{ev.date}</strong>
                </div>
                <div>
                  <h3>{ev.title}</h3>
                  <p>{ev.startTime ? `${ev.startTime}${ev.endTime ? ` - ${ev.endTime}` : ""}` : "All day"}</p>
                  {ev.location && <p className="event-location">{ev.location}</p>}
                </div>
              </div>
            ))}
          </div>
        )}

        
      </section>

      {/* schedule-side — 右側詳情面板 */}
      <aside className="schedule-side">
        <DetailPanel
          selectedEvent={selectedEvent}
          onEdit={(ev) => { setEditingEvent(ev); setIsModalOpen(true); }}
          onDelete={deleteEvent}
        />
      </aside>

      {/* EventModal */}
      {isModalOpen && (
        <EventModal
          editingEvent={editingEvent}
          currentMonth={currentMonth}
          currentYear={currentYear}
          onSubmit={(data) => {
            if (data.id) {
              updateEvent(data.id, data);
            } else {
              addEvent({ ...data, tone: eventTone(data.priority) } as Omit<ScheduleEvent, "id" | "participants">);
            }
            setEditingEvent(null);
            setIsModalOpen(false);
          }}
          onClose={() => { setIsModalOpen(false); setEditingEvent(null); }}
        />
      )}
    </div>
  );
}
