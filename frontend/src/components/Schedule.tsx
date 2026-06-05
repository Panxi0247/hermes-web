import { useMemo, useState } from "react";
import "./Schedule.css";
import AgendaList from "./schedule/AgendaList";
import CalendarView from "./schedule/CalendarView";
import WeekView from "./schedule/WeekView";
import DetailPanel from "./schedule/DetailPanel";
import EventModal from "./schedule/EventModal";
import { useScheduleEvents } from "./schedule/useScheduleEvents";
import type { EventFormData, ScheduleEvent, ScheduleView } from "./schedule/types";
import { eventTone, getCalendarDays, isToday as isTodayDate } from "./schedule/scheduleUtils";

export default function Schedule() {
  const [view, setView] = useState<ScheduleView>("calendar");
  const [searchQuery, setSearchQuery] = useState("");
  const [currentDate, setCurrentDate] = useState(() => new Date());
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<ScheduleEvent | null>(null);
  const { events, addEvent, updateEvent, deleteEvent } = useScheduleEvents();

  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth() + 1;

  const filteredEvents = useMemo(() => {
    if (!searchQuery.trim()) return events;
    const query = searchQuery.toLowerCase();
    return events.filter(
      (event) =>
        event.title.toLowerCase().includes(query) ||
        (event.location?.toLowerCase().includes(query) ?? false)
    );
  }, [events, searchQuery]);

  const selectedEvent = useMemo(
    () => events.find((event) => event.id === selectedEventId) ?? null,
    [events, selectedEventId]
  );

  const eventsByDay = useMemo(() => {
    const byDay = new Map<number, ScheduleEvent[]>();
    filteredEvents
      .filter((event) => event.month === currentMonth && event.year === currentYear)
      .forEach((event) => {
        byDay.set(event.date, [...(byDay.get(event.date) ?? []), event]);
      });
    return byDay;
  }, [currentMonth, currentYear, filteredEvents]);

  const calendarDays = useMemo(
    () => getCalendarDays(currentYear, currentMonth),
    [currentMonth, currentYear]
  );

  const openNewEventModal = () => {
    setEditingEvent(null);
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setEditingEvent(null);
    setIsModalOpen(false);
  };

  const handleSubmit = (data: EventFormData) => {
    if (data.id) {
      updateEvent(data.id, data);
    } else {
      addEvent({ ...data, tone: eventTone(data.priority) });
    }
    closeModal();
  };

  const handleDelete = (id: string) => {
    deleteEvent(id);
    setSelectedEventId((current) => (current === id ? null : current));
  };

  const selectFirstEventForDay = (day: number) => {
    setSelectedEventId(eventsByDay.get(day)?.[0]?.id ?? null);
  };

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
              <input
                placeholder="搜尋事件或活動"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </label>
            <button className="schedule-add" onClick={openNewEventModal}>+ Add</button>
          </div>
        </div>

        <div className="schedule-controls">
          <div className="view-switch">
            <button className={view === "calendar" ? "active" : ""} onClick={() => setView("calendar")}>Month</button>
            <button className={view === "week" ? "active" : ""} onClick={() => setView("week")}>Week</button>
            <button className={view === "agenda" ? "active" : ""} onClick={() => setView("agenda")}>Schedule</button>
          </div>
          <div className="month-control">
            <button onClick={() => setCurrentDate(new Date(currentYear, currentDate.getMonth() - 1, 1))}>‹</button>
            <strong>{currentYear} / {currentMonth.toString().padStart(2, "0")}</strong>
            <button onClick={() => setCurrentDate(new Date(currentYear, currentDate.getMonth() + 1, 1))}>›</button>
          </div>
        </div>

        {view === "calendar" ? (
          <CalendarView
            calendarDays={calendarDays}
            eventsForDay={(day) => eventsByDay.get(day) ?? []}
            isToday={(day) => isTodayDate(day, currentMonth, currentYear)}
            onSelectDay={selectFirstEventForDay}
            onSelectEvent={setSelectedEventId}
          />
        ) : view === "week" ? (
          <WeekView
            year={currentYear}
            month={currentMonth}
            date={currentDate.getDate()}
            eventsForDay={(day) => eventsByDay.get(day) ?? []}
            isToday={(day) => isTodayDate(day, currentMonth, currentYear)}
            onSelectDay={selectFirstEventForDay}
            onSelectEvent={setSelectedEventId}
          />
        ) : (
          <AgendaList
            events={filteredEvents}
            selectedEventId={selectedEventId}
            onSelectEvent={setSelectedEventId}
          />
        )}
      </section>

      <aside className="schedule-side">
        <DetailPanel
          selectedEvent={selectedEvent}
          onEdit={(event) => {
            setEditingEvent(event);
            setIsModalOpen(true);
          }}
          onDelete={handleDelete}
        />
      </aside>

      {isModalOpen && (
        <EventModal
          editingEvent={editingEvent}
          currentMonth={currentMonth}
          currentYear={currentYear}
          onSubmit={handleSubmit}
          onClose={closeModal}
        />
      )}
    </div>
  );
}
