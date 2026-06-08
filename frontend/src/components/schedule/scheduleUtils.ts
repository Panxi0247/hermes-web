import type { EventPriority, EventTone } from "./types";

export const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export const TONE_LABELS: Record<EventTone, string> = {
  IP4: "緊急",
  IP3: "重要",
  IP2: "一般",
  IP1: "輕緩",
};

export const TONE_COLORS: Record<EventTone, string> = {
  IP4: "var(--IP4, #ee7f95)",
  IP3: "var(--IP3, #f4c86a)",
  IP2: "var(--IP2, #64d2a4)",
  IP1: "var(--IP1, #80b7ff)",
};

export const generateId = () => Math.random().toString(36).slice(2, 10);

export function calcDuration(start: string, end: string) {
  const [startHours, startMinutes] = start.split(":").map(Number);
  const [endHours, endMinutes] = end.split(":").map(Number);
  const minutes = endHours * 60 + endMinutes - (startHours * 60 + startMinutes);

  if (minutes < 60) return `${minutes} min`;

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes ? `${hours} hr ${remainingMinutes} min` : `${hours} hr`;
}

export function eventTone(priority: EventPriority = "medium"): EventTone {
  if (priority === "high") return "IP4";
  if (priority === "low") return "IP1";
  return "IP2";
}

export function getCalendarDays(year: number, month: number): (number | null)[] {
  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDayOfWeek = new Date(year, month - 1, 1).getDay();

  return [
    ...Array(firstDayOfWeek).fill(null),
    ...Array.from({ length: daysInMonth }, (_, index) => index + 1),
  ];
}

export function isToday(day: number, month: number, year: number) {
  const today = new Date();
  return (
    day === today.getDate() &&
    month === today.getMonth() + 1 &&
    year === today.getFullYear()
  );
}
