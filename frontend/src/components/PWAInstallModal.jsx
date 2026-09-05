import React from 'react';
import {
  Smartphone,
  Share2,
  PlusSquare,
  Maximize2,
  Minimize2,
  X,
  CheckCircle2,
  Sparkles,
  Download,
} from 'lucide-react';

export default function PWAInstallModal({
  isOpen,
  onClose,
  onInstallNative,
  hasNativePrompt,
  guideType,
  onToggleFullscreen,
  isFullscreen,
}) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md bg-gradient-to-b from-slate-900 via-slate-950 to-black border border-amber-500/40 rounded-3xl p-6 shadow-2xl text-slate-100 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="pwa-modal-title"
      >
        {/* Glow effect */}
        <div className="absolute -top-20 -left-20 w-48 h-48 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-20 -right-20 w-48 h-48 bg-amber-600/10 rounded-full blur-3xl pointer-events-none" />

        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full text-slate-400 hover:text-white hover:bg-slate-800/60 transition cursor-pointer"
          aria-label="关闭"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3.5 mb-5">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center text-slate-950 shadow-glow-gold flex-shrink-0">
            <Smartphone className="w-6 h-6" />
          </div>
          <div>
            <h3 id="pwa-modal-title" className="text-lg font-black text-white flex items-center gap-1.5">
              安装 HPoker 到主屏幕
              <Sparkles className="w-4 h-4 text-amber-400 inline" />
            </h3>
            <p className="text-xs text-slate-400">无浏览器地址栏，全屏沉浸式极速游玩</p>
          </div>
        </div>

        {/* Content based on guideType */}
        {guideType === 'already_installed' ? (
          <div className="flex flex-col gap-4 py-2">
            <div className="flex items-center gap-3 p-3.5 bg-emerald-950/40 border border-emerald-500/40 rounded-2xl text-emerald-300 text-sm">
              <CheckCircle2 className="w-5 h-5 flex-shrink-0 text-emerald-400" />
              <span>当前已处于全屏或主屏幕独立应用模式中！</span>
            </div>
            <button
              type="button"
              onClick={onToggleFullscreen}
              className="w-full py-3 px-4 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-2xl font-bold text-sm text-amber-300 flex items-center justify-center gap-2 transition active:scale-98"
            >
              {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
              {isFullscreen ? '退出全屏' : '切换浏览器全屏'}
            </button>
          </div>
        ) : hasNativePrompt ? (
          <div className="flex flex-col gap-4">
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col gap-2.5 text-xs text-slate-300">
              <div className="flex items-center gap-2 text-amber-300 font-bold">
                <span>✨ 安装特权：</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-amber-400">●</span> 移除浏览器顶部网址栏与底部操作条，视野提升 20%
              </div>
              <div className="flex items-center gap-2">
                <span className="text-amber-400">●</span> 手机桌面一键秒开，自动保持登录与牌桌连接
              </div>
              <div className="flex items-center gap-2">
                <span className="text-amber-400">●</span> 禁用手势下拉刷新与误触，竞技更稳定
              </div>
            </div>

            <button
              type="button"
              onClick={onInstallNative}
              className="w-full py-3.5 px-5 bg-gradient-to-r from-amber-500 via-amber-400 to-amber-600 text-slate-950 font-black rounded-2xl shadow-glow-gold hover:brightness-110 active:scale-98 transition flex items-center justify-center gap-2 text-sm cursor-pointer"
            >
              <Download className="w-4 h-4 stroke-[2.5]" />
              立即添加到主屏幕
            </button>

            {onToggleFullscreen && (
              <button
                type="button"
                onClick={onToggleFullscreen}
                className="w-full py-2.5 px-4 bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800 rounded-xl text-xs font-bold text-slate-300 flex items-center justify-center gap-2 transition active:scale-98"
              >
                {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
                {isFullscreen ? '退出网页全屏' : '临时网页全屏'}
              </button>
            )}
          </div>
        ) : guideType === 'ios' ? (
          <div className="flex flex-col gap-4">
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col gap-3 text-xs text-slate-300">
              <div className="text-amber-300 font-bold mb-1">
                iPhone / iPad Safari 简易 3 步全屏安装：
              </div>
              <div className="flex items-start gap-2.5">
                <span className="flex items-center justify-center w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 font-black text-[11px] flex-shrink-0 mt-0.5">
                  1
                </span>
                <div>
                  点击 Safari 屏幕底部的「分享」按钮
                  <Share2 className="w-4 h-4 inline-block mx-1 text-sky-400" />
                </div>
              </div>
              <div className="flex items-start gap-2.5">
                <span className="flex items-center justify-center w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 font-black text-[11px] flex-shrink-0 mt-0.5">
                  2
                </span>
                <div>
                  在弹出菜单中向下轻滑，点击「添加到主屏幕」
                  <PlusSquare className="w-4 h-4 inline-block mx-1 text-amber-400" />
                </div>
              </div>
              <div className="flex items-start gap-2.5">
                <span className="flex items-center justify-center w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 font-black text-[11px] flex-shrink-0 mt-0.5">
                  3
                </span>
                <div>
                  点击右上角「添加」，回到桌面打开 HPoker 图标即可享受全屏！
                </div>
              </div>
            </div>

            {onToggleFullscreen && (
              <button
                type="button"
                onClick={onToggleFullscreen}
                className="w-full py-2.5 px-4 bg-slate-900/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-xs font-bold text-amber-400 flex items-center justify-center gap-2 transition active:scale-98"
              >
                {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
                {isFullscreen ? '退出全屏' : '试用全屏模式'}
              </button>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col gap-3 text-xs text-slate-300">
              <div className="text-amber-300 font-bold mb-1">
                浏览器添加到主屏幕指引：
              </div>
              <div className="flex items-start gap-2">
                <span className="text-amber-400">1.</span>
                <span>
                  点击浏览器右上角或底部的菜单图标（通常为「⋮」或「≡」）
                </span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-amber-400">2.</span>
                <span>选择「安装应用」或「添加到主屏幕」选项</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-amber-400">3.</span>
                <span>
                  若在微信或其他应用内打开，请先点击右上角选择「在系统浏览器中打开」
                </span>
              </div>
            </div>

            {onToggleFullscreen && (
              <button
                type="button"
                onClick={onToggleFullscreen}
                className="w-full py-3 px-4 bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 font-black rounded-2xl shadow-glow-gold hover:brightness-110 active:scale-98 transition flex items-center justify-center gap-2 text-sm cursor-pointer"
              >
                {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                {isFullscreen ? '退出全屏模式' : '进入全屏游玩模式'}
              </button>
            )}
          </div>
        )}

        {/* Footer info */}
        <div className="mt-5 pt-3 border-t border-slate-800/80 text-center">
          <p className="text-[11px] text-slate-500">
            支持 iOS Safari、Android Chrome、Edge 及各主流移动浏览器
          </p>
        </div>
      </div>
    </div>
  );
}
