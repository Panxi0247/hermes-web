import { memo } from "react";
import type { ScheduleEvent } from "./types";
import { calcDuration, TONE_COLORS } from "./scheduleUtils";

type DetailPanelProps = {
  selectedEvent: ScheduleEvent | null;
  onEdit: (event: ScheduleEvent) => void;
  onDelete: (id: string) => void;
};

const priorityLabel = (event: ScheduleEvent) => {
  if (event.priority === "high") return "★ High Priority";
  if (event.priority === "low") return "○ Low Priority";
  return "● Medium Priority";
};

const DetailPanel = memo(function DetailPanel({
  selectedEvent,
  onEdit,
  onDelete,
}: DetailPanelProps) {
  if (!selectedEvent) {
    return <div className="detail-card empty-panel"><p>Select an event to view details</p></div>;
  }

  const date = new Date(selectedEvent.year, selectedEvent.month - 1, selectedEvent.date);
  const dayOfWeek = date.toLocaleString("en-US", { weekday: "short" });
  const eventMonthName = date.toLocaleString("en-US", { month: "short" });

  const handleDelete = () => {
    if (confirm(`Delete "${selectedEvent.title}"?`)) onDelete(selectedEvent.id);
  };

  return (
    <>
      <div className="featured-event" style={{ borderLeftColor: TONE_COLORS[selectedEvent.tone] }}>
        <span>{priorityLabel(selectedEvent)}</span>
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
          <div>
            <dt>日期</dt>
            <dd>{dayOfWeek}, {eventMonthName} {selectedEvent.date}, {selectedEvent.year}</dd>
          </div>
          {selectedEvent.location && (
            <div>
              <dt>地點</dt>
              <dd>{selectedEvent.location}</dd>
            </div>
          )}
          {selectedEvent.startTime && selectedEvent.endTime && (
            <div>
              <dt>時長</dt>
              <dd>{calcDuration(selectedEvent.startTime, selectedEvent.endTime)}</dd>
            </div>
          )}
          {selectedEvent.description && (
            <div>
              <dt>說明</dt>
              <dd>{selectedEvent.description}</dd>
            </div>
          )}
        </dl>
        <div className="detail-actions">
          <button className="btn-edit" onClick={() => onEdit(selectedEvent)}>Edit</button>
          <button className="btn-delete" onClick={handleDelete}>Delete</button>
        </div>
      </div>
    </>
  );
});

export default DetailPanel;
