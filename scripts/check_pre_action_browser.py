"""Run with .venv/bin/python while Vite serves localhost:5174."""
import os
from playwright.sync_api import sync_playwright

HTML = '''<div id="root"></div><script type="module">
import RefreshRuntime from '/@react-refresh';
RefreshRuntime.injectIntoGlobalHook(window);
window.$RefreshReg$ = () => {};
window.$RefreshSig$ = () => type => type;
window.__vite_plugin_react_preamble_installed__ = true;
</script><script type="module">
import React from '/node_modules/.vite/deps/react.js';
import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
import ActionBar from '/src/components/ActionBar.jsx';
import '/src/index.css';
window.actions = [];
function App() {
 const [turn, setTurn] = React.useState(false);
 const [tick, setTick] = React.useState(0);
 window.turn = setTurn; window.refresh = () => setTick(n => n + 1);
 return React.createElement(ActionBar, {isMyTurn: turn, street:'PREFLOP', handNumber:1,
 selfSeat:{player_id:'a', chips:1000, has_cards:true}, isMobileMode:false,
 legalActions:turn ? {can_fold:true,can_check:true} : null,
 onAction:action => window.actions.push({action, at:performance.now()})});
}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(App));
</script>'''
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=os.environ.get("CHROMIUM_PATH"))
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.on("pageerror", lambda error: print(error, flush=True))
    page.on("console", lambda message: print(message.text, flush=True) if message.type == "error" else None)
    page.set_default_timeout(5000)
    page.route('**/pre-action-check', lambda route: route.fulfill(content_type='text/html', body=HTML))
    page.goto('http://127.0.0.1:5174/pre-action-check')
    page.get_by_role('button', name='过牌 / 弃牌').first.click()
    page.evaluate('window.started = performance.now(); window.turn(true)')
    page.wait_for_timeout(500)
    page.evaluate('window.refresh()')  # A fresh legalActions object must not cancel the timer.
    assert page.evaluate('actions.length') == 0
    page.wait_for_function('actions.length === 1')
    delay = page.evaluate('actions[0].at - started')
    assert 1000 <= delay <= 3300, delay
    assert page.evaluate('actions[0].action') == 'CHECK'
    page.evaluate('window.turn(false)')
    page.get_by_role('button', name='过牌 / 弃牌').first.click()
    page.evaluate('window.turn(true)')
    page.get_by_role('button', name='弃牌', exact=False).first.click()
    page.wait_for_timeout(3200)
    assert page.evaluate('actions.length') == 2
    page.evaluate('window.turn(false)')
    page.get_by_role('button', name='过牌 / 弃牌').first.click()
    page.evaluate('window.turn(true)')
    page.wait_for_timeout(100)
    page.evaluate('window.turn(false)')
    page.wait_for_timeout(3200)
    assert page.evaluate('actions.length') == 2
    browser.close()
print('Pre-action delay, rerender, manual cancellation and turn cancellation passed.')
