import { KeyRound, X } from "lucide-react";
import { useEffect, useState } from "react";

interface SettingsDialogProps {
  open: boolean;
  apiKey: string;
  onClose: () => void;
  onSave: (value: string) => void;
}

export function SettingsDialog({ open, apiKey, onClose, onSave }: SettingsDialogProps) {
  const [value, setValue] = useState(apiKey);

  useEffect(() => setValue(apiKey), [apiKey, open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="dialog-backdrop" onMouseDown={onClose}>
      <section
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="dialog__header">
          <div>
            <span className="dialog__eyebrow"><KeyRound size={15} />连接凭据</span>
            <h2 id="settings-title">API 设置</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="关闭设置"><X size={19} /></button>
        </div>
        <label className="field-label" htmlFor="api-key">Demo API Key</label>
        <input
          id="api-key"
          className="text-input"
          type="password"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="dev 模式可留空"
          autoComplete="off"
          autoFocus
        />
        <p className="field-help">凭据仅保存在当前浏览器标签页会话中。</p>
        <div className="dialog__actions">
          <button className="button button--secondary" onClick={onClose}>取消</button>
          <button className="button button--primary" onClick={() => onSave(value)}>保存</button>
        </div>
      </section>
    </div>
  );
}
