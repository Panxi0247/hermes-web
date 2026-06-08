import "./Settings.css";

// TODO: 期末階段擴充 - 引入 Hermes 使用者身份與 Personal Memory 設定
//  current: 所有點擊均為 static placeholder，未對接後端
export default function Settings() {
  return (
    <div className="settings">
      <div className="settings-header">
        <p className="eyebrow">Settings</p>
        <h2>設定</h2>
      </div>

      <div className="settings-list">
        <div className="settings-item">
          <div className="settings-item-icon">U</div>
          <div className="settings-item-text">
            <strong>User</strong>
            <span>個人帳戶與資訊</span>
          </div>
          <span className="settings-arrow">›</span>
        </div>

        <div className="settings-item">
          <div className="settings-item-icon">T</div>
          <div className="settings-item-text">
            <strong>Trust website</strong>
            <span>網站信任與安全性設定</span>
          </div>
          <span className="settings-arrow">›</span>
        </div>

        <div className="settings-item">
          <div className="settings-item-icon">I</div>
          <div className="settings-item-text">
            <strong>Swich User Identity</strong>
            <span>切換使用者身份</span>
          </div>
          <span className="settings-arrow">›</span>
        </div>

        <div className="settings-item">
          <div className="settings-item-icon">M</div>
          <div className="settings-item-text">
            <strong>Personal Memory</strong>
            <span>個人化記憶設定</span>
          </div>
          <span className="settings-arrow">›</span>
        </div>

        <div className="settings-item">
          <div className="settings-item-icon">L</div>
          <div className="settings-item-text">
            <strong>Login / Out</strong>
            <span>登入與登出</span>
          </div>
          <span className="settings-arrow">›</span>
        </div>
      </div>
    </div>
  );
}