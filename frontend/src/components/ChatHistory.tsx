import type { Conversation } from "../types";
import { formatConversationTime, previewText } from "../storage/conversations";

interface ChatHistoryProps {
  conversations: Conversation[];
  onLoadConversation: (conversation: Conversation) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string) => void;
}

export default function ChatHistory({
  conversations,
  onLoadConversation,
  onNewConversation,
  onDeleteConversation,
}: ChatHistoryProps) {
  const handleDelete = (id: string, event: React.MouseEvent) => {
    event.stopPropagation();
    onDeleteConversation(id);
  };

  return (
    <div className="chat-history">
      <div className="history-header">
        <div>
          <p className="eyebrow">History</p>
          <h2>歷史紀錄</h2>
        </div>
        <button className="btn-new-chat" onClick={onNewConversation}>+ 新對話</button>
      </div>

      <div className="history-list">
        {conversations.length === 0 && (
          <div className="history-empty">
            <strong>尚無對話紀錄</strong>
            <span>開始聊天後，對話會自動保存在這裡。</span>
          </div>
        )}

        {conversations.map((conversation) => (
          <div
            key={conversation.id}
            className="history-item"
            onClick={() => onLoadConversation(conversation)}
          >
            <div className="history-item-content">
              <div className="history-title">
                {conversation.title || previewText(conversation.messages)}
              </div>
              <div className="history-time">
                {formatConversationTime(conversation.updatedAt)}
              </div>
            </div>
            <button
              className="history-delete"
              onClick={(event) => handleDelete(conversation.id, event)}
              aria-label="刪除"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
