import React, { useState } from 'react';
import {
  Smartphone,
  Share2,
  PlusSquare,
  Download,
  Compass,
  Copy,
  Check,
  Sparkles,
  AlertTriangle,
  ExternalLink,
  ShieldCheck,
} from 'lucide-react';

export default function MobilePWAGate({
  isIOS = false,
  isInAppBrowser = false,
  hasNativePrompt = false,
  onInstallNative,
}) {
  const [activeTab, setActiveTab] = useState(isIOS ? 'ios' : 'android');
  const [copied, setCopied] = useState(false);

  const handleCopyUrl = async () => {
    try {
      const url = typeof window !== 'undefined' ? window.location.href : '';
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(url);
      } else {
        const input = document.createElement('input');
        input.value = url;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (err) {
      console.warn('[PWA] Copy URL failed:', err);
    }
  };

  return (
    <div className="fixed inset-0 z-[999] w-full h-full bg-[#080b11] text-slate-100 flex flex-col justify-between overflow-y-auto overscroll-contain p-4 sm:p-6 font-sans select-none">
      {/* Background Ambience Glow */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-96 h-96 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="fixed bottom-0 right-0 w-80 h-80 bg-amber-600/10 rounded-full blur-3xl pointer-events-none" />

      {/* Main Content Container */}
      <div className="relative z-10 w-full max-w-md mx-auto flex flex-col gap-4 my-auto py-2">
        {/* Branding & Logo */}
        <div className="flex flex-col items-center text-center gap-2">
          <div className="relative flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-400 via-amber-600 to-amber-800 shadow-glow-gold border-2 border-amber-300/40">
            <span className="text-3xl filter drop-shadow">♠️</span>
            <span className="absolute -top-1.5 -right-1.5 flex h-4 w-4">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-4 w-4 bg-amber-500 border border-slate-950"></span>
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-950/80 border border-amber-500/50 text-[11px] font-black text-amber-300">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>手机端仅支持桌面应用 (PWA) 启动</span>
          </div>

          <h1 className="text-xl sm:text-2xl font-black tracking-wide text-white">
            HPoker 德州扑克
          </h1>
          <p className="text-xs text-slate-400 max-w-xs leading-relaxed">
            为保证 100% 全屏竞技、无网址栏遮挡与极速稳定连接，手机端已开启沉浸式应用模式。
          </p>
        </div>

        {/* Mandatory Native Browser Warning Banner */}
        <div className="p-3.5 rounded-2xl bg-gradient-to-r from-amber-950/90 via-slate-900 to-amber-950/90 border border-amber-500/60 shadow-lg flex items-start gap-3 text-left">
          <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div className="flex flex-col gap-0.5 text-xs">
            <span className="font-black text-amber-300">
              必须使用手机自带浏览器打开本站
            </span>
            <span className="text-slate-300 leading-relaxed text-[11px]">
              微信、QQ 等内置浏览器无法安装主屏应用。请在手机系统自带浏览器中打开本站以完成安装。
            </span>
          </div>
        </div>

        {/* In-App Browser (WeChat/QQ/etc.) Urgent Alert */}
        {isInAppBrowser && (
          <div className="p-3.5 rounded-2xl bg-red-950/80 border-2 border-red-500/70 shadow-glow-red flex flex-col gap-2.5 text-left animate-pulse">
            <div className="flex items-center gap-2 text-xs font-black text-red-200">
              <ExternalLink className="w-4 h-4 text-red-400" />
              <span>检测到您当前在应用内置浏览器中</span>
            </div>
            <p className="text-[11px] text-red-300 leading-relaxed">
              请点击屏幕右上角的 <strong className="text-white">「···」</strong> 菜单，选择 <strong className="text-white">「在浏览器中打开」</strong> 或 <strong className="text-white">「在 Safari 中打开」</strong>！
            </p>
            <button
              type="button"
              onClick={handleCopyUrl}
              className="w-full py-2 px-3 rounded-xl bg-slate-900 border border-amber-500/50 text-amber-300 hover:bg-slate-800 text-xs font-bold flex items-center justify-center gap-1.5 transition active:scale-98"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4 text-amber-400" />}
              <span>{copied ? '网址已复制到剪贴板' : '复制网址并在自带浏览器中粘贴'}</span>
            </button>
          </div>
        )}

        {/* OS Platform Selector Tabs */}
        <div className="grid grid-cols-2 gap-2 p-1 bg-slate-950/80 rounded-2xl border border-slate-800">
          <button
            type="button"
            onClick={() => setActiveTab('ios')}
            className={`py-2 px-3 rounded-xl text-xs font-black transition flex items-center justify-center gap-1.5 cursor-pointer ${
              activeTab === 'ios'
                ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 shadow-md'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <span>🍎 苹果 iPhone / Safari</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('android')}
            className={`py-2 px-3 rounded-xl text-xs font-black transition flex items-center justify-center gap-1.5 cursor-pointer ${
              activeTab === 'android'
                ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 shadow-md'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <span>🤖 安卓 Android / Chrome</span>
          </button>
        </div>

        {/* Tab 1: iOS Safari Installation Steps */}
        {activeTab === 'ios' && (
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col gap-3 text-left">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800 text-xs">
              <span className="font-black text-amber-300 flex items-center gap-1">
                <Compass className="w-4 h-4 text-sky-400" />
                苹果自带 Safari 安装步骤
              </span>
              <span className="text-[10px] text-slate-500 font-bold">仅需 3 秒</span>
            </div>

            <div className="flex flex-col gap-2.5 text-xs text-slate-300">
              <div className="flex items-start gap-2.5">
                <span className="flex items-center justify-center w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 font-black text-[11px] flex-shrink-0 mt-0.5">
                  1
                </span>
                <div className="leading-relaxed">
                  在手机系统自带 <strong className="text-white">Safari 浏览器</strong> 中打开本网址
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <span className="flex items-center justify-center w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 font-black text-[11px] flex-shrink-0 mt-0.5">
                  2
                </span>
                <div className="leading-relaxed">
                  点击 Safari 屏幕底部的 <strong className="text-sky-300">「分享」</strong> 按钮
                  <Share2 className="w-3.5 h-3.5 inline-block mx-1 text-sky-400" />
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <span className="flex items-center justify-center w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 font-black text-[11px] flex-shrink-0 mt-0.5">
                  3
                </span>
                <div className="leading-relaxed">
                  向上轻滑菜单，选择 <strong className="text-amber-300">「添加到主屏幕」</strong>
                  <PlusSquare className="w-3.5 h-3.5 inline-block mx-1 text-amber-400" />
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <span className="flex items-center justify-center w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 font-black text-[11px] flex-shrink-0 mt-0.5">
                  4
                </span>
                <div className="leading-relaxed">
                  点击右上角 <strong className="text-emerald-300">「添加」</strong>，返回桌面打开 <strong className="text-amber-300">「HPoker」</strong> 图标立即畅玩！
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Android Installation Steps */}
        {activeTab === 'android' && (
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col gap-3 text-left">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800 text-xs">
              <span className="font-black text-amber-300 flex items-center gap-1">
                <Smartphone className="w-4 h-4 text-emerald-400" />
                安卓系统 / Chrome 安装步骤
              </span>
              <span className="text-[10px] text-slate-500 font-bold">推荐自带浏览器</span>
            </div>

            {hasNativePrompt && onInstallNative ? (
              <div className="flex flex-col gap-2">
                <button
                  type="button"
                  onClick={onInstallNative}
                  className="w-full py-3 px-4 bg-gradient-to-r from-amber-500 via-amber-400 to-amber-600 text-slate-950 font-black rounded-xl shadow-glow-gold hover:brightness-110 active:scale-98 transition flex items-center justify-center gap-2 text-xs cursor-pointer"
                >
                  <Download className="w-4 h-4 stroke-[2.5]" />
                  <span>立即安装到手机桌面 (点击安装)</span>
                </button>
                <span className="text-[10px] text-center text-slate-400">
                  点击后在系统弹出窗口中确认「安装」即可
                </span>
              </div>
            ) : (
              <div className="flex flex-col gap-2.5 text-xs text-slate-300">
                <div className="flex items-start gap-2.5">
                  <span className="flex items-center justify-center w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 font-black text-[11px] flex-shrink-0 mt-0.5">
                    1
                  </span>
                  <div className="leading-relaxed">
                    在手机自带浏览器或 <strong className="text-white">Chrome</strong> 中打开本网址
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <span className="flex items-center justify-center w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 font-black text-[11px] flex-shrink-0 mt-0.5">
                    2
                  </span>
                  <div className="leading-relaxed">
                    点击右上角或底部菜单按钮 <strong className="text-amber-300">「⋮」</strong> 或 <strong className="text-amber-300">「≡」</strong>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <span className="flex items-center justify-center w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 font-black text-[11px] flex-shrink-0 mt-0.5">
                    3
                  </span>
                  <div className="leading-relaxed">
                    选择 <strong className="text-amber-300">「安装应用」</strong> 或 <strong className="text-amber-300">「添加到主屏幕」</strong>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <span className="flex items-center justify-center w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 font-black text-[11px] flex-shrink-0 mt-0.5">
                    4
                  </span>
                  <div className="leading-relaxed">
                    确认添加后，返回手机桌面点击 <strong className="text-amber-300">「HPoker」</strong> 图标启动！
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Quick URL Copy Action */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleCopyUrl}
            className="flex-1 py-2.5 px-3 rounded-xl bg-slate-900/90 border border-slate-700 hover:border-amber-500/50 text-slate-300 hover:text-amber-300 text-xs font-bold flex items-center justify-center gap-1.5 transition active:scale-98"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
            <span>{copied ? '已复制网址' : '复制网址到系统自带浏览器打开'}</span>
          </button>
        </div>

        {/* Already Installed Helper */}
        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 text-center flex flex-col gap-1">
          <span className="text-[11px] font-bold text-slate-400 flex items-center justify-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            已经添加到主屏幕？
          </span>
          <span className="text-[10px] text-slate-500 leading-relaxed">
            按下手机 Home 键或返回桌面，点击桌面上的「HPoker」图标即可自动启动并进入对局！
          </span>
        </div>
      </div>

      {/* Footer */}
      <footer className="relative z-10 w-full text-center py-2 text-[10px] text-slate-600">
        HPoker 德州扑克 · PWA 沉浸式竞技桌面应用
      </footer>
    </div>
  );
}
