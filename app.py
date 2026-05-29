"""考勤打卡系统 - 主应用"""
from flask import Flask, request, render_template_string, send_from_directory
from config import Config
from models import db
from wechat_handler import verify_signature, parse_xml, handle_message
from admin_api import admin_bp
import os

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

# 初始化数据库
db.init_app(app)

# 注册蓝图
app.register_blueprint(admin_bp)


with app.app_context():
    db.create_all()


# ==================== 微信接入 ====================

@app.route("/wechat", methods=["GET", "POST"])
def wechat():
    """微信公众号接入与消息处理"""
    if request.method == "GET":
        # 服务器验证
        signature = request.args.get("signature", "")
        timestamp = request.args.get("timestamp", "")
        nonce = request.args.get("nonce", "")
        echostr = request.args.get("echostr", "")

        if verify_signature(signature, timestamp, nonce):
            return echostr
        return "signature verification failed"

    # POST - 接收消息
    xml_data = request.data
    msg = parse_xml(xml_data)

    if not msg:
        return "success"

    to_user = msg.get("FromUserName", "")
    from_user = msg.get("ToUserName", "")

    try:
        reply_content = handle_message(msg)
    except Exception as e:
        reply_content = f"系统异常：{str(e)}，请联系管理员"

    # 构建回复
    reply = f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{msg.get('CreateTime', '')}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{reply_content}]]></Content>
</xml>"""

    return reply, 200, {"Content-Type": "application/xml; charset=utf-8"}


# ==================== 管理后台页面 ====================

ADMIN_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>考勤管理系统 - 管理后台</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; min-height: 100vh; }
        
        /* 登录页 */
        .login-container { display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .login-box { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.1); width: 360px; }
        .login-box h1 { text-align: center; margin-bottom: 8px; color: #1a1a1a; font-size: 24px; }
        .login-box .subtitle { text-align: center; color: #666; margin-bottom: 28px; font-size: 14px; }
        .login-box input { width: 100%; padding: 12px 16px; border: 1px solid #ddd; border-radius: 8px; font-size: 15px; margin-bottom: 16px; outline: none; transition: border-color 0.2s; }
        .login-box input:focus { border-color: #4472C4; }
        .login-box button { width: 100%; padding: 12px; background: #4472C4; color: white; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; transition: background 0.2s; }
        .login-box button:hover { background: #3461a8; }
        .login-error { color: #e74c3c; text-align: center; margin-top: 12px; font-size: 14px; display: none; }

        /* 主界面 */
        .app-container { display: none; }
        .header { background: white; padding: 0 24px; height: 56px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 1px 4px rgba(0,0,0,0.08); position: sticky; top: 0; z-index: 100; }
        .header h2 { font-size: 18px; color: #1a1a1a; }
        .header .logout-btn { padding: 6px 16px; background: #f0f0f0; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
        .header .logout-btn:hover { background: #e0e0e0; }

        .tabs { display: flex; gap: 4px; background: white; padding: 0 24px; border-bottom: 1px solid #e8e8e8; }
        .tab { padding: 12px 20px; cursor: pointer; color: #666; font-size: 14px; border-bottom: 2px solid transparent; transition: all 0.2s; }
        .tab:hover { color: #4472C4; }
        .tab.active { color: #4472C4; border-bottom-color: #4472C4; font-weight: 600; }

        .content { padding: 20px 24px; max-width: 1400px; margin: 0 auto; }
        .panel { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); margin-bottom: 20px; }
        .panel h3 { font-size: 16px; margin-bottom: 16px; color: #1a1a1a; }

        /* 工具栏 */
        .toolbar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 16px; }
        .toolbar select, .toolbar input { padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; outline: none; }
        .toolbar select:focus, .toolbar input:focus { border-color: #4472C4; }
        .toolbar input[type="date"] { width: 140px; }
        .btn { padding: 8px 16px; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; transition: all 0.2s; }
        .btn-primary { background: #4472C4; color: white; }
        .btn-primary:hover { background: #3461a8; }
        .btn-success { background: #27ae60; color: white; }
        .btn-success:hover { background: #219a52; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-danger:hover { background: #c0392b; }
        .btn-warning { background: #f39c12; color: white; }
        .btn-warning:hover { background: #d68910; }
        .btn-sm { padding: 4px 10px; font-size: 12px; }

        /* 表格 */
        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        th, td { padding: 10px 12px; text-align: center; border-bottom: 1px solid #f0f0f0; }
        th { background: #fafafa; font-weight: 600; color: #555; white-space: nowrap; }
        tr:hover td { background: #f8f9ff; }
        .text-left { text-align: left; }
        .text-right { text-align: right; }
        .text-muted { color: #999; }
        .text-danger { color: #e74c3c; }
        .text-success { color: #27ae60; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
        .badge-workday { background: #e8f5e9; color: #2e7d32; }
        .badge-weekend { background: #fff3e0; color: #e65100; }
        .badge-holiday { background: #fce4ec; color: #c62828; }

        /* 弹窗 */
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; justify-content: center; align-items: center; }
        .modal.show { display: flex; }
        .modal-box { background: white; border-radius: 12px; padding: 28px; width: 460px; max-height: 80vh; overflow-y: auto; }
        .modal-box h3 { margin-bottom: 20px; }
        .modal-box label { display: block; margin-bottom: 6px; font-size: 14px; color: #555; }
        .modal-box input, .modal-box select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; margin-bottom: 14px; outline: none; }
        .modal-box input:focus, .modal-box select:focus { border-color: #4472C4; }
        .modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 8px; }
        .modal-box .btn { min-width: 80px; }

        /* 统计卡片 */
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px; }
        .stat-card { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
        .stat-card .label { font-size: 13px; color: #999; margin-bottom: 6px; }
        .stat-card .value { font-size: 28px; font-weight: 700; color: #1a1a1a; }
        .stat-card .unit { font-size: 14px; color: #666; font-weight: 400; }

        .msg { padding: 10px 16px; border-radius: 6px; margin-bottom: 12px; font-size: 14px; display: none; }
        .msg-success { background: #e8f5e9; color: #2e7d32; }
        .msg-error { background: #fce4ec; color: #c62828; }
    </style>
</head>
<body>
    <!-- 登录页 -->
    <div id="loginPage" class="login-container">
        <div class="login-box">
            <h1>📋 考勤管理系统</h1>
            <p class="subtitle">管理员登录</p>
            <input type="password" id="password" placeholder="请输入管理密码" onkeydown="if(event.key==='Enter')login()">
            <button onclick="login()">登 录</button>
            <p id="loginError" class="login-error">密码错误</p>
        </div>
    </div>

    <!-- 主界面 -->
    <div id="appPage" class="app-container">
        <div class="header">
            <h2>📋 考勤管理系统</h2>
            <button class="logout-btn" onclick="logout()">退出登录</button>
        </div>
        <div class="tabs">
            <div class="tab active" onclick="switchTab('summary')">考勤汇总</div>
            <div class="tab" onclick="switchTab('records')">打卡记录</div>
            <div class="tab" onclick="switchTab('users')">员工管理</div>
            <div class="tab" onclick="switchTab('holidays')">节假日管理</div>
        </div>
        <div class="content" id="tabContent"></div>
    </div>

    <!-- 补卡弹窗 -->
    <div class="modal" id="manualModal">
        <div class="modal-box">
            <h3>补卡操作</h3>
            <label>员工</label>
            <select id="manualUserId"></select>
            <label>日期</label>
            <input type="date" id="manualDate">
            <label>上班时间</label>
            <input type="time" id="manualCheckIn" value="09:00">
            <label>下班时间</label>
            <input type="time" id="manualCheckOut" value="18:00">
            <label>备注</label>
            <input type="text" id="manualRemark" value="管理员补卡">
            <div class="modal-actions">
                <button class="btn" onclick="closeModal('manualModal')">取消</button>
                <button class="btn btn-primary" onclick="submitManual()">确认补卡</button>
            </div>
        </div>
    </div>

    <!-- 设置底薪弹窗 -->
    <div class="modal" id="salaryModal">
        <div class="modal-box">
            <h3>设置底薪</h3>
            <label>底薪（元/月）</label>
            <input type="number" id="salaryInput" min="0" step="100">
            <div class="modal-actions">
                <button class="btn" onclick="closeModal('salaryModal')">取消</button>
                <button class="btn btn-primary" onclick="submitSalary()">保存</button>
            </div>
        </div>
    </div>

    <div id="msgBox" class="msg"></div>

    <script>
        let currentTab = 'summary';
        let allUsers = [];

        // ========== 登录 ==========
        async function checkLogin() {
            const res = await fetch('/api/check_login');
            const data = await res.json();
            if (data.logged_in) showApp();
        }

        async function login() {
            const pwd = document.getElementById('password').value;
            const res = await fetch('/api/login', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: pwd })
            });
            const data = await res.json();
            if (data.code === 0) {
                showApp();
            } else {
                document.getElementById('loginError').style.display = 'block';
            }
        }

        async function logout() {
            await fetch('/api/logout', { method: 'POST' });
            document.getElementById('loginPage').style.display = 'flex';
            document.getElementById('appPage').style.display = 'none';
        }

        function showApp() {
            document.getElementById('loginPage').style.display = 'none';
            document.getElementById('appPage').style.display = 'block';
            loadUsers().then(() => switchTab('summary'));
        }

        // ========== Tab切换 ==========
        function switchTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            if (typeof event !== 'undefined' && event && event.target) {
                event.target.classList.add('active');
            } else {
                document.querySelectorAll('.tab').forEach(t => {
                    if (t.textContent.includes(tab === 'summary' ? '考勤汇总' : tab === 'records' ? '打卡记录' : tab === 'users' ? '员工管理' : '节假日管理')) {
                        t.classList.add('active');
                    }
                });
            }
            if (tab === 'summary') loadSummary();
            else if (tab === 'records') loadRecords();
            else if (tab === 'users') loadUsersTab();
            else if (tab === 'holidays') loadHolidays();
        }

        // ========== 加载用户列表 ==========
        async function loadUsers() {
            const res = await fetch('/api/users');
            const data = await res.json();
            allUsers = data.data || [];
        }

        // ========== 考勤汇总 ==========
        async function loadSummary() {
            const res = await fetch('/api/summary');
            const data = await res.json();
            const summaries = data.data || [];
            const period = data.period || {};

            let totalPay = 0, totalOT = 0;
            summaries.forEach(s => { totalPay += s.total_overtime_pay; totalOT += s.total_overtime_hours; });

            let html = `
                <div class="stats">
                    <div class="stat-card"><div class="label">当前考勤周期</div><div class="value" style="font-size:18px">${period.start} ~ ${period.end}</div></div>
                    <div class="stat-card"><div class="label">总加班时长</div><div class="value">${totalOT.toFixed(1)}<span class="unit">小时</span></div></div>
                    <div class="stat-card"><div class="label">总加班费</div><div class="value">${totalPay.toFixed(2)}<span class="unit">元</span></div></div>
                </div>
                <div class="panel">
                    <div class="toolbar">
                        <select id="summaryUser" onchange="loadSummaryByUser()">
                            <option value="">全部员工</option>
                        </select>
                        <input type="text" id="summaryCycle" placeholder="如: 2026年4月" style="width:120px">
                        <button class="btn btn-primary" onclick="loadSummaryByUser()">查询</button>
                        <input type="date" id="summaryStart" style="width:140px">
                        <span>~</span>
                        <input type="date" id="summaryEnd" style="width:140px">
                        <button class="btn btn-primary" onclick="loadSummaryByRange()">自定义查询</button>
                        <button class="btn btn-success" onclick="exportExcel()">导出Excel</button>
                    </div>
                    <table id="summaryTable"></table>
                </div>`;

            document.getElementById('tabContent').innerHTML = html;

            // 填充用户下拉
            const sel = document.getElementById('summaryUser');
            sel.innerHTML = '<option value="">全部员工</option>';
            allUsers.forEach(u => {
                sel.innerHTML += `<option value="${u.id}">${u.nickname}</option>`;
            });

            renderSummaryTable(summaries);
        }

        function renderSummaryTable(summaries) {
            let rows = '';
            summaries.forEach(s => {
                rows += `<tr>
                    <td>${s.nickname}</td>
                    <td>${s.base_salary.toFixed(0)}</td>
                    <td>${s.workday_count}</td>
                    <td>${s.total_work_hours.toFixed(1)}</td>
                    <td class="text-danger">${s.total_overtime_hours.toFixed(1)}</td>
                    <td class="text-success"><b>${s.total_overtime_pay.toFixed(2)}</b></td>
                </tr>`;
            });
            document.getElementById('summaryTable').innerHTML = `
                <thead><tr>
                    <th>姓名</th><th>底薪</th><th>出勤天数</th><th>工时(h)</th><th>加班(h)</th><th>加班费(元)</th>
                </tr></thead><tbody>${rows || '<tr><td colspan="6" class="text-muted">暂无数据</td></tr>'}</tbody>`;
        }

        async function loadSummaryByUser() {
            const uid = document.getElementById('summaryUser').value;
            const cycle = document.getElementById('summaryCycle').value;
            let url = '/api/summary?';
            if (uid) url += `user_id=${uid}&`;
            if (cycle) url += `cycle=${encodeURIComponent(cycle)}&`;

            const res = await fetch(url);
            const data = await res.json();
            renderSummaryTable(data.data || []);
        }

        async function loadSummaryByRange() {
            const uid = document.getElementById('summaryUser').value;
            const start = document.getElementById('summaryStart').value;
            const end = document.getElementById('summaryEnd').value;
            if (!start || !end) { showMsg('请选择起止日期', 'error'); return; }

            let url = `/api/summary?start_date=${start}&end_date=${end}`;
            if (uid) url += `&user_id=${uid}`;

            const res = await fetch(url);
            const data = await res.json();
            renderSummaryTable(data.data || []);
        }

        function exportExcel() {
            const uid = document.getElementById('summaryUser')?.value || '';
            const cycle = document.getElementById('summaryCycle')?.value || '';
            const start = document.getElementById('summaryStart')?.value || '';
            const end = document.getElementById('summaryEnd')?.value || '';

            let url = '/api/export?';
            if (uid) url += `user_id=${uid}&`;
            if (cycle) url += `cycle=${encodeURIComponent(cycle)}&`;
            if (start && end) url += `start_date=${start}&end_date=${end}&`;

            window.open(url, '_blank');
        }

        // ========== 打卡记录 ==========
        async function loadRecords() {
            let html = `
                <div class="panel">
                    <div class="toolbar">
                        <select id="recordUser" onchange="loadRecordsData()">
                            <option value="">全部员工</option>
                        </select>
                        <input type="date" id="recordStart">
                        <span>~</span>
                        <input type="date" id="recordEnd">
                        <button class="btn btn-primary" onclick="loadRecordsData()">查询</button>
                        <button class="btn btn-warning" onclick="showManualModal()">补卡</button>
                    </div>
                    <table id="recordsTable"></table>
                </div>`;

            document.getElementById('tabContent').innerHTML = html;

            const sel = document.getElementById('recordUser');
            sel.innerHTML = '<option value="">全部员工</option>';
            allUsers.forEach(u => {
                sel.innerHTML += `<option value="${u.id}">${u.nickname}</option>`;
            });

            loadRecordsData();
        }

        async function loadRecordsData() {
            const uid = document.getElementById('recordUser').value;
            const start = document.getElementById('recordStart').value;
            const end = document.getElementById('recordEnd').value;

            let url = '/api/records?';
            if (uid) url += `user_id=${uid}&`;
            if (start) url += `start_date=${start}&`;
            if (end) url += `end_date=${end}&`;

            const res = await fetch(url);
            const data = await res.json();
            const records = data.data || [];

            let rows = '';
            records.forEach(r => {
                rows += `<tr>
                    <td>${r.nickname}</td>
                    <td>${r.date}</td>
                    <td>${r.check_in || '-'}</td>
                    <td>${r.check_out || '-'}</td>
                    <td>${r.work_hours}</td>
                    <td>${r.overtime_hours}</td>
                    <td>${r.overtime_pay}</td>
                    <td>${r.is_manual ? '<span class="badge badge-weekend">补卡</span>' : '<span class="badge badge-workday">正常</span>'}</td>
                    <td>${r.remark || ''}</td>
                    <td><button class="btn btn-danger btn-sm" onclick="deleteRecord(${r.id})">删除</button></td>
                </tr>`;
            });

            document.getElementById('recordsTable').innerHTML = `
                <thead><tr>
                    <th>姓名</th><th>日期</th><th>上班</th><th>下班</th><th>工时</th><th>加班</th><th>加班费</th><th>类型</th><th>备注</th><th>操作</th>
                </tr></thead><tbody>${rows || '<tr><td colspan="10" class="text-muted">暂无记录</td></tr>'}</tbody>`;
        }

        async function deleteRecord(id) {
            if (!confirm('确定删除此条记录吗？')) return;
            await fetch(`/api/records/${id}`, { method: 'DELETE' });
            loadRecordsData();
            showMsg('已删除', 'success');
        }

        // ========== 补卡 ==========
        function showManualModal() {
            const sel = document.getElementById('manualUserId');
            sel.innerHTML = allUsers.map(u => `<option value="${u.id}">${u.nickname}</option>`).join('');
            document.getElementById('manualDate').value = new Date().toISOString().split('T')[0];
            document.getElementById('manualModal').classList.add('show');
        }

        async function submitManual() {
            const body = {
                user_id: parseInt(document.getElementById('manualUserId').value),
                date: document.getElementById('manualDate').value,
                check_in: document.getElementById('manualCheckIn').value,
                check_out: document.getElementById('manualCheckOut').value,
                remark: document.getElementById('manualRemark').value,
            };

            const res = await fetch('/api/records/manual', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            closeModal('manualModal');
            showMsg(data.msg, data.code === 0 ? 'success' : 'error');
            loadRecordsData();
        }

        // ========== 员工管理 ==========
        async function loadUsersTab() {
            let rows = '';
            allUsers.forEach(u => {
                rows += `<tr>
                    <td>${u.nickname}</td>
                    <td>${u.openid.substring(0, 16)}...</td>
                    <td>${u.base_salary.toFixed(0)}</td>
                    <td>${(u.base_salary / 21.75 / 8).toFixed(2)}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="showSalaryModal(${u.id}, ${u.base_salary})">设置底薪</button>
                        <button class="btn btn-sm btn-warning" onclick="renameUser(${u.id}, '${u.nickname}')">改名</button>
                    </td>
                </tr>`;
            });

            document.getElementById('tabContent').innerHTML = `
                <div class="panel">
                    <h3>员工列表</h3>
                    <p style="color:#999;font-size:13px;margin-bottom:16px">员工通过关注公众号自动注册，发送"设置用户名 张三"可自行设置名字</p>
                    <table>
                        <thead><tr><th>姓名</th><th>OpenID</th><th>底薪(元/月)</th><th>时薪(元/h)</th><th>操作</th></tr></thead>
                        <tbody>${rows || '<tr><td colspan="5" class="text-muted">暂无员工</td></tr>'}</tbody>
                    </table>
                </div>`;
        }

        function showSalaryModal(userId, currentSalary) {
            window._editUserId = userId;
            document.getElementById('salaryInput').value = currentSalary;
            document.getElementById('salaryModal').classList.add('show');
        }

        async function submitSalary() {
            const uid = window._editUserId;
            const salary = parseFloat(document.getElementById('salaryInput').value);
            await fetch(`/api/users/${uid}/salary`, {
                method: 'PUT', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ base_salary: salary })
            });
            closeModal('salaryModal');
            showMsg('底薪已更新', 'success');
            await loadUsers();
            loadUsersTab();
        }

        async function renameUser(userId, currentName) {
            const newName = prompt('请输入新名字：', currentName);
            if (!newName || newName === currentName) return;
            await fetch(`/api/users/${userId}/nickname`, {
                method: 'PUT', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nickname: newName })
            });
            showMsg('名字已更新', 'success');
            await loadUsers();
            loadUsersTab();
        }

        // ========== 节假日管理 ==========
        async function loadHolidays() {
            const year = new Date().getFullYear();
            const res = await fetch(`/api/holidays?year=${year}`);
            const data = await res.json();
            const holidays = data.data || [];

            let rows = '';
            holidays.forEach(h => {
                rows += `<tr>
                    <td>${h.date}</td><td>${h.name || '-'}</td>
                    <td><button class="btn btn-danger btn-sm" onclick="deleteHoliday(${h.id})">删除</button></td>
                </tr>`;
            });

            document.getElementById('tabContent').innerHTML = `
                <div class="panel">
                    <div class="toolbar">
                        <input type="date" id="holidayDate">
                        <input type="text" id="holidayName" placeholder="节日名称（可选）" style="width:160px">
                        <button class="btn btn-primary" onclick="addHoliday()">添加节假日</button>
                        <button class="btn btn-warning" onclick="batchHoliday()">批量导入</button>
                    </div>
                    <table>
                        <thead><tr><th>日期</th><th>名称</th><th>操作</th></tr></thead>
                        <tbody>${rows || '<tr><td colspan="3" class="text-muted">暂无节假日</td></tr>'}</tbody>
                    </table>
                </div>`;
        }

        async function addHoliday() {
            const date = document.getElementById('holidayDate').value;
            const name = document.getElementById('holidayName').value;
            if (!date) { showMsg('请选择日期', 'error'); return; }

            const res = await fetch('/api/holidays', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ date, name })
            });
            const data = await res.json();
            showMsg(data.msg, data.code === 0 ? 'success' : 'error');
            loadHolidays();
        }

        async function batchHoliday() {
            const input = prompt('请输入节假日日期，每行一个（格式：YYYY-MM-DD）:\n示例:\n2026-01-01\n2026-01-02\n2026-01-03');
            if (!input) return;
            const dates = input.split('\n').map(s => s.trim()).filter(s => s);
            const name = prompt('节日名称（可选）：', '法定节假日') || '法定节假日';

            const res = await fetch('/api/holidays/batch', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dates, name })
            });
            const data = await res.json();
            showMsg(data.msg, 'success');
            loadHolidays();
        }

        async function deleteHoliday(id) {
            if (!confirm('确定删除吗？')) return;
            await fetch(`/api/holidays/${id}`, { method: 'DELETE' });
            showMsg('已删除', 'success');
            loadHolidays();
        }

        // ========== 工具函数 ==========
        function closeModal(id) {
            document.getElementById(id).classList.remove('show');
        }

        function showMsg(msg, type) {
            const box = document.getElementById('msgBox');
            box.textContent = msg;
            box.className = 'msg msg-' + type;
            box.style.display = 'block';
            setTimeout(() => box.style.display = 'none', 3000);
        }

        // 初始化
        checkLogin();
    </script>
</body>
</html>"""


@app.route("/admin")
def admin_page():
    """管理后台页面"""
    return render_template_string(ADMIN_PAGE)


@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>考勤打卡系统</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; }
        .card { background: white; border-radius: 16px; padding: 40px; box-shadow: 0 20px 60px rgba(0,0,0,0.2); text-align: center; max-width: 480px; width: 90%; }
        .card h1 { font-size: 28px; margin-bottom: 8px; color: #1a1a1a; }
        .card p { color: #666; margin-bottom: 24px; font-size: 15px; }
        .card .info { background: #f8f9ff; border-radius: 10px; padding: 20px; margin: 20px 0; text-align: left; }
        .card .info h3 { margin-bottom: 12px; color: #4472C4; }
        .card .info ul { list-style: none; }
        .card .info li { padding: 6px 0; font-size: 14px; color: #555; }
        .card .info li::before { content: '▸ '; color: #4472C4; }
        .card .links { display: flex; gap: 12px; justify-content: center; margin-top: 20px; }
        .card .links a { padding: 10px 24px; border-radius: 8px; text-decoration: none; font-size: 14px; transition: all 0.2s; }
        .btn-primary { background: #4472C4; color: white; }
        .btn-primary:hover { background: #3461a8; }
        .btn-outline { border: 2px solid #4472C4; color: #4472C4; }
        .btn-outline:hover { background: #f0f4ff; }
    </style>
</head>
<body>
    <div class="card">
        <h1>📋 考勤打卡系统</h1>
        <p>微信公众号考勤管理</p>
        <div class="info">
            <h3>公众号功能</h3>
            <ul>
                <li>发送「上班」- 上班打卡</li>
                <li>发送「下班」- 下班打卡</li>
                <li>发送「查询」- 查看今日考勤</li>
                <li>发送「汇总」- 本月考勤汇总</li>
                <li>发送「底薪」- 查看底薪配置</li>
                <li>发送「设置用户名 张三」- 设置名字</li>
                <li>发送「帮助」- 功能列表</li>
            </ul>
        </div>
        <div class="links">
            <a href="/admin" class="btn-primary">管理后台</a>
            <a href="https://mp.weixin.qq.com/" target="_blank" class="btn-outline">微信公众平台</a>
        </div>
    </div>
</body>
</html>
""")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
