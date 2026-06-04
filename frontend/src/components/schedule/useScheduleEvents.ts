import { useEffect, useState } from "react";
import type { EventFormData, ScheduleEvent } from "./types";
import { generateId } from "./scheduleUtils";

const STORAGE_KEY = "hermes-schedule-events";

function loadEvents(): ScheduleEvent[] {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return [];
    const parsed = JSON.parse(saved);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function useScheduleEvents() {
  const [events, setEvents] = useState<ScheduleEvent[]>(loadEvents);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(events));
  }, [events]);

  const addEvent = (data: EventFormData) => {
    setEvents((previous) => [
      ...previous,
      { ...data, id: generateId(), participants: [] },
    ]);
  };

  const updateEvent = (id: string, data: Partial<ScheduleEvent>) => {
    setEvents((previous) =>
      previous.map((event) => (event.id === id ? { ...event, ...data } : event))
    );
  };

  const deleteEvent = (id: string) => {
    setEvents((previous) => previous.filter((event) => event.id !== id));
  };

  return {
    events,
    addEvent,
    updateEvent,
    deleteEvent,
  };
}
