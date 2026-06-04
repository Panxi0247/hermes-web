import { memo, useState } from "react";
import type { FormEvent } from "react";
import type { EventFormData, EventPriority, EventTone, ScheduleEvent } from "./types";

type EventModalProps = {
  editingEvent: ScheduleEvent | null;
  currentMonth: number;
  currentYear: number;
  onSubmit: (data: EventFormData) => void;
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

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return;

    onSubmit({
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
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(event) => event.stopPropagation()}>
        <h2>{editingEvent ? "Edit Event" : "New Event"}</h2>
        <form onSubmit={handleSubmit} className="event-form">
          <label>
            Title *
            <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Event title" required autoFocus />
          </label>
          <label>
            Date *
            <input type="number" min={1} max={31} value={date} onChange={(event) => setDate(Number(event.target.value))} required />
          </label>
          <div className="form-row">
            <label>
              Start
              <input type="time" value={startTime} onChange={(event) => setStartTime(event.target.value)} />
            </label>
            <label>
              End
              <input type="time" value={endTime} onChange={(event) => setEndTime(event.target.value)} />
            </label>
          </div>
          <label>
            Location
            <input value={location} onChange={(event) => setLocation(event.target.value)} placeholder="Location..." />
          </label>
          <label>
            Description
            <textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Details..." rows={3} />
          </label>
          <div className="form-row">
            <label>
              Tone
              <select value={tone} onChange={(event) => setTone(event.target.value as EventTone)}>
                <option value="IP4">IP4</option>
                <option value="IP3">IP3</option>
                <option value="IP2">IP2</option>
                <option value="IP1">IP1</option>
              </select>
            </label>
            <label>
              Priority
              <select value={priority} onChange={(event) => setPriority(event.target.value as EventPriority)}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
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

export default EventModal;
