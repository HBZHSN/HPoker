import React, { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Save } from 'lucide-react';
import {
  DEFAULT_ROOM_CONFIG,
  ROOM_DEFAULT_LIMITS,
  normalizeRoomDefaults,
} from '../utils/roomDefaults';

export default function AdminRoomDefaultsSettings({ token, onUpdated }) {
  const [config, setConfig] = useState(() => normalizeRoomDefaults(DEFAULT_ROOM_CONFIG));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    let active = true;
    const loadConfig = async () => {
      setLoading(true);
      setError('');
      try {
        const response = await fetch('/api/config/room-defaults', {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || '获取默认房间配置失败');
        if (active) setConfig(normalizeRoomDefaults(data));
      } catch (loadError) {
        if (active) setError(loadError.message || '获取默认房间配置失败');
      } finally {
        if (active) setLoading(false);
      }
    };

    loadConfig();
    return () => {
      active = false;
    };
  }, [token]);

  const updateField = (field, value) => {
    setConfig((current) => ({ ...current, [field]: value }));
    setError('');
    setSuccess('');
  };

  const handleSave = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');

    const normalized = normalizeRoomDefaults(config);
    const payload = {
      buyin_chips: normalized.buyin_chips,
      cash_value: normalized.cash_value,
      small_blind: normalized.small_blind,
      action_timeout: normalized.action_timeout,
      max_seats: normalized.max_seats,
      assistant_win_ratio: normalized.assistant_win_ratio,
    };

    try {
      const response = await fetch('/api/admin/config/room-defaults', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '保存默认房间配置失败');

      const savedConfig = normalizeRoomDefaults(data);
      setConfig(savedConfig);
      onUpdated?.(savedConfig);
      setSuccess('默认房间配置已更新');
    } catch (saveError) {
      setError(saveError.message || '保存默认房间配置失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      onSubmit={handleSave}
      className="flex-shrink-0 rounded-2xl border border-amber-500/30 bg-slate-900/90 p-4 shadow-xl"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-xs font-black uppercase tracking-wide text-amber-300">
            默认房间配置
          </div>
          <div className="mt-1 text-[11px] text-slate-500">
            仅影响之后创建的房间，已有房间不变
          </div>
        </div>
        <button
          type="submit"
          disabled={loading || saving}
          className="flex items-center gap-1.5 rounded-xl bg-amber-500 px-3.5 py-1.5 text-xs font-black text-slate-950 shadow transition hover:bg-amber-400 disabled:cursor-wait disabled:opacity-50"
        >
          <Save className="h-3.5 w-3.5" />
          {saving ? '保存中...' : '保存'}
        </button>
      </div>

      {error && (
        <div className="mb-3 flex items-center gap-2 rounded-xl border border-red-500/60 bg-red-950/80 p-2.5 text-xs font-bold text-red-300">
          <AlertCircle className="h-4 w-4 flex-shrink-0 text-red-400" />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="mb-3 flex items-center gap-2 rounded-xl border border-emerald-500/60 bg-emerald-950/80 p-2.5 text-xs font-bold text-emerald-300">
          <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-emerald-400" />
          <span>{success}</span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs font-bold text-slate-300">
          <span>买入筹码</span>
          <input
            type="number"
            min={ROOM_DEFAULT_LIMITS.buyin_chips.min}
            step="1"
            value={config.buyin_chips}
            onChange={(event) => updateField('buyin_chips', Number(event.target.value))}
            className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 font-bold text-slate-100 outline-none transition focus:border-amber-400"
          />
        </label>

        <label className="flex flex-col gap-1 text-xs font-bold text-slate-300">
          <span>H币（0 为娱乐局）</span>
          <input
            type="number"
            min={ROOM_DEFAULT_LIMITS.cash_value.min}
            step="0.01"
            value={config.cash_value}
            onChange={(event) => updateField('cash_value', Number(event.target.value))}
            className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 font-bold text-slate-100 outline-none transition focus:border-amber-400"
          />
        </label>

        <label className="flex flex-col gap-1 text-xs font-bold text-slate-300">
          <span>小盲 SB</span>
          <input
            type="number"
            min={ROOM_DEFAULT_LIMITS.small_blind.min}
            step="1"
            value={config.small_blind}
            onChange={(event) => updateField('small_blind', Number(event.target.value))}
            className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 font-bold text-slate-100 outline-none transition focus:border-amber-400"
          />
        </label>

        <div className="flex flex-col gap-1 text-xs font-bold text-slate-300">
          <span>大盲 BB</span>
          <div className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-amber-300">
            {config.big_blind}
          </div>
        </div>

        <label className="flex flex-col gap-1 text-xs font-bold text-slate-300">
          <span>行动限时（秒）</span>
          <input
            type="number"
            min={ROOM_DEFAULT_LIMITS.action_timeout.min}
            max={ROOM_DEFAULT_LIMITS.action_timeout.max}
            step="1"
            value={config.action_timeout}
            onChange={(event) => updateField('action_timeout', Number(event.target.value))}
            className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 font-bold text-slate-100 outline-none transition focus:border-amber-400"
          />
        </label>

        <label className="flex flex-col gap-1 text-xs font-bold text-slate-300">
          <span>人数</span>
          <select
            value={config.max_seats}
            onChange={(event) => updateField('max_seats', Number(event.target.value))}
            className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 font-bold text-slate-100 outline-none transition focus:border-amber-400"
          >
            {Array.from(
              {
                length: ROOM_DEFAULT_LIMITS.max_seats.max - ROOM_DEFAULT_LIMITS.max_seats.min + 1,
              },
              (_, index) => index + ROOM_DEFAULT_LIMITS.max_seats.min,
            ).map((seatCount) => (
              <option key={seatCount} value={seatCount}>{seatCount} 人桌</option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-300 sm:col-span-2">
          <span className="flex items-center justify-between">
            <span>辅助折算</span>
            <span className="font-mono text-amber-300">{config.assistant_win_pct}%</span>
          </span>
          <input
            type="range"
            min={ROOM_DEFAULT_LIMITS.assistant_win_ratio.min * 100}
            max={ROOM_DEFAULT_LIMITS.assistant_win_ratio.max * 100}
            step="5"
            value={config.assistant_win_pct}
            onChange={(event) => updateField('assistant_win_ratio', Number(event.target.value) / 100)}
            className="accent-amber-400"
          />
        </label>
      </div>
    </form>
  );
}
