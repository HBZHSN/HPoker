import React, { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Save } from 'lucide-react';
import {
  DEFAULT_WATERMARK_CONFIG,
  WATERMARK_LIMITS,
  normalizeWatermarkConfig,
} from '../utils/watermark';

export default function AdminWatermarkSettings({ token, onUpdated }) {
  const [config, setConfig] = useState(DEFAULT_WATERMARK_CONFIG);
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
        const response = await fetch('/api/config/watermark', {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || '获取水印配置失败');
        if (active) setConfig(normalizeWatermarkConfig(data));
      } catch (loadError) {
        if (active) setError(loadError.message || '获取水印配置失败');
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

    const payload = normalizeWatermarkConfig(config);
    try {
      const response = await fetch('/api/admin/config/watermark', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '保存水印配置失败');

      const savedConfig = normalizeWatermarkConfig(data);
      setConfig(savedConfig);
      onUpdated?.(savedConfig);
      setSuccess('水印配置已更新');
    } catch (saveError) {
      setError(saveError.message || '保存水印配置失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      onSubmit={handleSave}
      className="flex-shrink-0 rounded-2xl border border-sky-500/30 bg-slate-900/90 p-4 shadow-xl"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-xs font-black uppercase tracking-wide text-sky-300">
            全局水印
          </div>
          <div className="mt-1 text-[11px] text-slate-500">
            所有已登录用户可见，仅管理员可修改
          </div>
        </div>
        <button
          type="submit"
          disabled={loading || saving}
          className="flex items-center gap-1.5 rounded-xl bg-sky-600 px-3.5 py-1.5 text-xs font-black text-white shadow transition hover:bg-sky-500 disabled:cursor-wait disabled:opacity-50"
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
        <label className="flex flex-col gap-1 text-xs font-bold text-slate-300 sm:col-span-2">
          <span>文本内容</span>
          <input
            type="text"
            value={config.text}
            maxLength={200}
            onChange={(event) => updateField('text', event.target.value)}
            placeholder="清空文本可隐藏水印"
            className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 font-bold text-slate-100 outline-none transition focus:border-sky-400"
          />
        </label>

        <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-300">
          <span className="flex items-center justify-between">
            <span>不透明度</span>
            <span className="font-mono text-sky-300">{Math.round(config.opacity * 100)}%</span>
          </span>
          <input
            type="range"
            min={WATERMARK_LIMITS.opacity.min}
            max={WATERMARK_LIMITS.opacity.max}
            step="0.01"
            value={config.opacity}
            onChange={(event) => updateField('opacity', Number(event.target.value))}
            className="accent-sky-400"
          />
        </label>

        <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-300">
          <span className="flex items-center justify-between">
            <span>密度（横竖屏自适应）</span>
            <span className="font-mono text-sky-300">基准 {config.density}</span>
          </span>
          <input
            type="range"
            min={WATERMARK_LIMITS.density.min}
            max={WATERMARK_LIMITS.density.max}
            step="1"
            value={config.density}
            onChange={(event) => updateField('density', Number(event.target.value))}
            className="accent-sky-400"
          />
        </label>

        <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-300 sm:col-span-2">
          <span className="flex items-center justify-between">
            <span>倾斜</span>
            <span className="font-mono text-sky-300">{config.tilt}°</span>
          </span>
          <input
            type="range"
            min={WATERMARK_LIMITS.tilt.min}
            max={WATERMARK_LIMITS.tilt.max}
            step="1"
            value={config.tilt}
            onChange={(event) => updateField('tilt', Number(event.target.value))}
            className="accent-sky-400"
          />
        </label>
      </div>
    </form>
  );
}
