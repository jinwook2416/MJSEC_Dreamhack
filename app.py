import sqlite3, os, json, uuid, shutil, binascii, subprocess
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "MJSEC_SUPER_SECRET_KEY")

# 파일 업로드 경로 설정
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def init_db():
    if os.path.exists('database.db'):
        os.remove('database.db')
    conn = sqlite3.connect('database.db')

    if os.path.exists(UPLOAD_FOLDER):
        shutil.rmtree(UPLOAD_FOLDER)
    os.makedirs(UPLOAD_FOLDER)

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # 유저 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (uid TEXT PRIMARY KEY, username TEXT, pw TEXT, permission TEXT)''')
    
    # 문제 업로드 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS challenges 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  title TEXT, content TEXT, filename TEXT, flag TEXT)''')

    admin_pw = binascii.hexlify(os.urandom(4)).decode("utf8")
    admin_uid = str(uuid.uuid4())
    c.execute(f'INSERT INTO users(uid, username, pw, permission) values("{admin_uid}", "admin", "{admin_pw}", "admin")')
    guest_uid = str(uuid.uuid4())
    c.execute(f'INSERT INTO users(uid, username, pw, permission) values("{guest_uid}", "guest", "guest", "user")')
    guest2_uid = str(uuid.uuid4())
    c.execute(f'INSERT INTO users(uid, username, pw, permission) values("{guest2_uid}", "guest2", "guest2", "user")')


    flag_path = os.path.join(UPLOAD_FOLDER, 'flag.txt')
    with open(flag_path, 'w') as f:
        f.write('DH{welcome_to_mjsec_dreamhack}')

    c.execute('''INSERT INTO challenges (title, content, filename, flag) VALUES (?, ?, ?, ?)''',
              ('Welcome MJSEC!', 
               'MJSEC Dreamhack에 오신 것을 환영합니다!', 
               'flag.txt', 'DH{welcome_to_mjsec_dreamhack}'))
    
    conn.commit()
    conn.close()

init_db()

def get_current_user():
    uid = session.get("uid")
    if not uid: return None
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    user = conn.execute(f"SELECT * FROM users WHERE uid = '{uid}'").fetchone()
    conn.close()
    return user


@app.route('/')
def index():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    return render_template('index.html', user=user)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get("username", "").strip()
        password = request.form.get("password")
        
        if not username or not password:
            return render_template("signup.html", error="입력값이 부족합니다.")

        uid = str(uuid.uuid4())
        pw = password

        users = (
            f'{{"permission":"user",'
            f'"username":"{username}",'
            f'"pw":"{pw}",'
            f'"uid":"{uid}"}}'
        )

        try:
            user_json = json.loads(users) 
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            conn.execute(f"INSERT INTO users VALUES ('{user_json['uid']}', '{user_json['username']}', '{user_json['pw']}', '{user_json['permission']}')")
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except Exception:
            return render_template("signup.html", error="회원가입 실패")
            
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        query = f"SELECT * FROM users WHERE username = '{username}' AND pw = '{password}'"
        
        try:
            user = conn.execute(query).fetchone()
            conn.close()
            if user:
                session["uid"] = user["uid"]
                return redirect(url_for('index'))
            return render_template('login.html', error="로그인 실패")
        except Exception:
            return render_template('login.html', error="로그인 실패")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/list')
def problem_list():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row 
    problems = conn.execute('SELECT * FROM challenges').fetchall()
    conn.close()
    return render_template('list.html', problems=problems)

@app.route('/register', methods=['GET', 'POST'])
def register():
    user = get_current_user()
    if not user or user['permission'] != 'admin':
        return "<script>alert('관리자 권한이 필요합니다.'); location.href='/';</script>"

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        flag = request.form['flag']
        file = request.files.get('file')
        
        filename = ''
        if file and file.filename != '':
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        conn = sqlite3.connect('database.db')
        conn.execute(f"INSERT INTO challenges (title, content, filename, flag) VALUES ('{title}', '{content}', '{filename}', '{flag}')")
        conn.commit()
        conn.close()
        return redirect(url_for('problem_list'))
        
    return render_template('register.html')

@app.route('/solve/<int:problem_id>', methods=['GET', 'POST'])
def solve(problem_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    problem = conn.execute('SELECT * FROM challenges WHERE id = ?', (problem_id,)).fetchone()
    conn.close()

    if request.method == 'POST':
        data = request.get_json()
        user_flag = data.get('flag')
        if user_flag == problem['flag']:
            return jsonify({'success': True, 'message': 'Correct Flag!'})
        else:
            return jsonify({'success': False, 'message': 'Wrong Flag. Try Again!'})

    return render_template('solve.html', problem=problem)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/execute/<filename>')
def execute_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not os.path.exists(file_path):
        return "<script>alert('파일을 찾을 수 없습니다.'); history.back();</script>"

    if filename.endswith('.py'):
        try:
            result = subprocess.check_output(
                ['python3', filename], 
                stderr=subprocess.STDOUT, 
                timeout=5,
                cwd=app.config['UPLOAD_FOLDER'] 
            )
            output = result.decode('utf-8')
            title = f"Python Script Execution: {filename}"
            theme_color = "#00ff00"
        except subprocess.TimeoutExpired:
            output = "Error: Execution timed out (5s limit)."
            title = "Timeout Error"
            theme_color = "#ff4444"
        except subprocess.CalledProcessError as e:
            output = e.output.decode('utf-8')
            title = "Execution Error"
            theme_color = "#ff4444"
        except Exception as e:
            output = str(e)
            title = "System Error"
            theme_color = "#ff4444"

    else:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                output = f.read()
            title = f"File Content: {filename}"
            theme_color = "#007bff" 
        except Exception as e:
            output = f"파일을 읽을 수 없습니다: {str(e)}"
            title = "Read Error"
            theme_color = "#ff4444"

    return f"""
    <body style="background-color: #1a1a1a; color: white; padding: 30px; font-family: 'Courier New', monospace; line-height: 1.6;">
        <h2 style="color: {theme_color};">{title}</h2>
        <hr style="border-color: #444;">
        <div style="background-color: #000; padding: 20px; border-radius: 5px; border: 1px solid #333; min-height: 300px; white-space: pre-wrap; font-size: 1.1rem; color: #eee;">{output}</div>
        <br>
        <button onclick="window.close()" style="background:#333; color:white; border:1px solid #555; padding:10px 20px; cursor:pointer; border-radius: 5px; font-weight: bold;">Close</button>
    </body>
    """

if __name__ == '__main__':
    host_addr = os.getenv('FLASK_HOST', '0.0.0.0')
    app.run(host=host_addr, port=5000, debug=True)