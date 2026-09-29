"""Browser regressions; run with Vite at localhost:5174 and optional CHROMIUM_PATH."""
import os
from playwright.sync_api import sync_playwright

HTML = '''<div id="root"></div><script type="module">
import RefreshRuntime from '/@react-refresh';
RefreshRuntime.injectIntoGlobalHook(window);
window.$RefreshReg$ = () => {}; window.$RefreshSig$ = () => type => type;
window.__vite_plugin_react_preamble_installed__ = true;
</script><script type="module">
import React from '/node_modules/.vite/deps/react.js';
import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
import HandResultModal from '/src/components/HandResultModal.jsx';
import PokerTable from '/src/components/PokerTable.jsx';
import {HandHistoryPanel} from '/src/components/PersonalHistory.jsx';
import '/src/index.css';
const card = {rank:14,suit:'spades',rank_symbol:'A',suit_symbol:'♠'};
const me = {player_id:'a',name:'Alice',chips:100,hole_cards:[card],shown_cards:[],seat_index:0};
const opponent = {player_id:'b',name:'Bob',chips:100,hole_cards:[],shown_cards:[],seat_index:1};
const results = [me,opponent].map(p=>({...p,total_bet:10,payout_amount:10,net_profit:0,hand_desc:'一对'}));
window.ready = []; window.events = [];
function App() {
 const [shown,setShown] = React.useState(false);
 const [mode,setMode] = React.useState('modal');
 const [street,setStreet] = React.useState('HAND_END');
 window.reveal=setShown; window.mode=setMode; window.street=setStreet;
 const handResults=results.map(p=>({...p,shown_cards:shown&&p.player_id==='b'?[card]:[]}));
 if(mode==='history') return React.createElement(HandHistoryPanel,{token:'test',userId:'a'});
 if(mode==='table') return React.createElement(PokerTable,{room:{room_id:'test',config:{},table:{street,hand_number:street==='HAND_END'?1:2,hand_results:street==='HAND_END'?handResults:[],seats:[me,opponent],board_cards:[],total_pot:20}},currentUser:{user_id:'a'},onSendWsEvent:(...args)=>window.events.push(args)});
 return React.createElement(HandResultModal,{isOpen:true,handResults,selfSeat:me,onClose:()=>{},onToggleReady:()=>window.ready.push(Date.now()),readOnly:mode==='review'});
}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(App));
</script>'''
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=os.environ.get('CHROMIUM_PATH'))
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.set_default_timeout(5000)
    page.route('**/hand-review-check', lambda route: route.fulfill(content_type='text/html', body=HTML))
    page.clock.install()
    page.goto('http://127.0.0.1:5174/hand-review-check')
    page.get_by_role('dialog').wait_for()
    for _ in range(4):
        page.clock.run_for(1000)
    assert page.get_by_text('1s 后自动准备', exact=True).is_visible()
    page.evaluate('window.reveal(true)')
    page.get_by_text('3s 后自动准备', exact=True).wait_for()
    page.clock.run_for(2900)
    assert page.evaluate('ready.length') == 0
    page.clock.run_for(200)
    assert page.evaluate('ready.length') == 1
    page.evaluate("window.mode('review')")
    page.get_by_role('dialog', name='上一局', exact=True).wait_for()
    assert page.get_by_role('checkbox').count() == 0
    page.keyboard.press('Space')
    page.clock.run_for(6000)
    assert page.evaluate('ready.length') == 1
    page.evaluate("window.mode('table')")
    page.get_by_role('dialog').wait_for()
    page.evaluate("window.street('PREFLOP')")
    page.get_by_role('dialog').wait_for(state='hidden')
    page.get_by_role('button', name='上一局', exact=True).click()
    page.get_by_role('dialog', name='上一局', exact=True).wait_for()
    assert page.get_by_text('第 1 局', exact=True).is_visible()
    page.keyboard.press('Escape')
    page.get_by_role('dialog').wait_for(state='hidden')
    for width in (320, 390):
        page.set_viewport_size({'width':width,'height':844})
        page.get_by_role('button', name='上一局', exact=True).click()
        page.get_by_role('dialog', name='上一局', exact=True).wait_for()
        page.keyboard.press('Escape')
    page.route('**/api/hands/my?*', lambda route: route.fulfill(json={
        'total': 1, 'summary': {'net_chips': 10}, 'hands': [{
            'hand_id': 'test:1', 'hand_number': 1, 'room_name': 'Test', 'ended_at': 1000,
            'hole_cards': [], 'board': [], 'actions': [], 'net_chips': 10,
            'opponents': [{'player_id': 'b', 'player_name': 'Bob', 'net_chips': -10,
                'shown_cards': [{'rank': 13, 'suit': 'hearts'}], 'hand_description': '一对 K'}],
        }],
    }))
    page.evaluate("window.mode('history')")
    page.get_by_text('一对 K', exact=True).wait_for()
    assert page.get_by_text('K♥', exact=True).is_visible()
    assert not errors, errors
    browser.close()
print('Reveal countdown, read-only review, last-hand snapshot and mobile entry passed.')
