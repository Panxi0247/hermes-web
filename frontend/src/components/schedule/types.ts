export type EventTone = "IP1" | "IP2" | "IP3" | "IP4";
export type EventPriority = "low" | "medium" | "high";
export type ScheduleView = "agenda" | "calendar";

export type Participant = {
  id: string;
  name: string;
};

export type ScheduleEvent = {
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

export type EventFormData = Omit<ScheduleEvent, "id" | "participants"> & {
  id?: string;
};
