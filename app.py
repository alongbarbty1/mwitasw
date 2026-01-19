from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import requests
import os
import json
import base64
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid
import re

app = Flask(__name__)
CORS(app)

# Configuration - use environment variable for API key
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "🔐🔐🔐🔐🔐")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Create uploads directory
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx',
    'ppt', 'pptx', 'csv', 'json', 'xml', 'md', 'py', 'js', 'html', 'css',
    'java', 'cpp', 'c', 'go', 'rs', 'php', 'rb', 'ts', 'jsx', 'tsx'
}

# Session-based memory storage
chat_sessions = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_uploaded_file(file):
    """Process uploaded files and extract text content"""
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # For text files, read content
        if filename.rsplit('.', 1)[1].lower() in ['txt', 'md', 'csv', 'json', 'xml', 'py', 'js', 'html', 'css', 'java', 'cpp', 'c', 'go', 'rs', 'php', 'rb', 'ts', 'jsx', 'tsx']:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read(10000)  # Read first 10000 chars
                return {
                    'type': 'text_file',
                    'filename': filename,
                    'content': content[:2000] + '...' if len(content) > 2000 else content,
                    'size': os.path.getsize(filepath),
                    'path': filepath
                }
            except UnicodeDecodeError:
                # Try different encoding
                with open(filepath, 'r', encoding='latin-1') as f:
                    content = f.read(10000)
                return {
                    'type': 'text_file',
                    'filename': filename,
                    'content': content[:2000] + '...' if len(content) > 2000 else content,
                    'size': os.path.getsize(filepath),
                    'path': filepath
                }
        else:
            # For other files, return metadata
            return {
                'type': 'file',
                'filename': filename,
                'mimetype': file.mimetype,
                'size': os.path.getsize(filepath),
                'path': filepath
            }
    except Exception as e:
        return {'error': str(e)}

def ask_ai_stream(messages, session_id):
    """Stream AI response using Server-Sent Events"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ai-chat-render.onrender.com",
        "X-Title": "Pro AI Chat",
    }
    
    payload = {
        "model": "deepseek/deepseek-r1-0528:free",
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, stream=True, timeout=60)
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]
                    if data != '[DONE]':
                        try:
                            chunk = json.loads(data)
                            if 'choices' in chunk and chunk['choices'][0]['delta'].get('content'):
                                yield chunk['choices'][0]['delta']['content']
                        except:
                            continue
    except Exception as e:
        yield f"❌ Error: {str(e)}"

def ask_ai(messages):
    """Regular AI call (non-streaming)"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ai-chat-render.onrender.com",
        "X-Title": "Pro AI Chat",
    }
    
    payload = {
        "model": "deepseek/deepseek-r1-0528:free",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ Error connecting to AI: {str(e)}"

def format_response(text):
    """Format AI response with proper markdown"""
    # Convert **bold** to HTML
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    # Convert *italic* to HTML
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    # Convert code blocks
    text = re.sub(r'```(\w+)?\n(.*?)```', r'<pre><code class="language-\1">\2</code></pre>', text, flags=re.DOTALL)
    # Convert inline code
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    # Convert lists
    lines = text.split('\n')
    formatted_lines = []
    in_list = False
    
    for line in lines:
        if line.strip().startswith('- ') or line.strip().startswith('* '):
            if not in_list:
                formatted_lines.append('<ul>')
                in_list = True
            formatted_lines.append(f'<li>{line.strip()[2:]}</li>')
        elif line.strip().startswith(('1. ', '2. ', '3. ', '4. ', '5. ', '6. ', '7. ', '8. ', '9. ')):
            if not in_list:
                formatted_lines.append('<ol>')
                in_list = True
            formatted_lines.append(f'<li>{line.strip()[2:]}</li>')
        else:
            if in_list:
                formatted_lines.append('</ul>' if line.strip().startswith('- ') else '</ol>')
                in_list = False
            formatted_lines.append(line)
    
    if in_list:
        formatted_lines.append('</ul>')
    
    return '\n'.join(formatted_lines)

# Serve static files
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Main route
@app.route('/')
def index():
    return render_template('index.html')

# Health check endpoint for Render
@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

# Initialize chat session
@app.route('/api/init', methods=['POST'])
def init_chat():
    session_id = str(uuid.uuid4())
    chat_sessions[session_id] = {
        'memory': [],
        'created_at': datetime.now().isoformat(),
        'files': []
    }
    return jsonify({'session_id': session_id, 'status': 'created'})

# Clear chat history
@app.route('/api/clear', methods=['POST'])
def clear_chat():
    data = request.get_json()
    session_id = data.get('session_id')
    if session_id in chat_sessions:
        chat_sessions[session_id]['memory'] = []
        chat_sessions[session_id]['files'] = []
    return jsonify({'status': 'cleared'})

# File upload endpoint
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        file_info = process_uploaded_file(file)
        session_id = request.form.get('session_id')
        
        if session_id and session_id in chat_sessions:
            chat_sessions[session_id]['files'].append(file_info)
            # Add file info to memory
            file_message = {
                'role': 'user',
                'content': f"Uploaded file: {file_info['filename']}\nType: {file_info.get('type', 'unknown')}\nSize: {file_info.get('size', 0)} bytes"
            }
            if 'content' in file_info:
                file_message['content'] += f"\nContent preview:\n{file_info['content']}"
            
            chat_sessions[session_id]['memory'].append(file_message)
        
        return jsonify({
            'success': True,
            'filename': file_info['filename'],
            'type': file_info.get('type', 'file'),
            'preview': file_info.get('content', '')[:500] if 'content' in file_info else None
        })
    
    return jsonify({'error': 'File type not allowed'}), 400

# Streaming chat endpoint
@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    data = request.get_json()
    session_id = data.get('session_id')
    user_message = data.get('message', '').strip()
    
    if not session_id or session_id not in chat_sessions:
        return jsonify({'error': 'Invalid session'}), 400
    
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    
    # Add user message to memory
    chat_sessions[session_id]['memory'].append({'role': 'user', 'content': user_message})
    
    def generate():
        full_response = ""
        for chunk in ask_ai_stream(chat_sessions[session_id]['memory'], session_id):
            full_response += chunk
            yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
        
        # Add assistant response to memory
        chat_sessions[session_id]['memory'].append({'role': 'assistant', 'content': full_response})
        yield f"data: {json.dumps({'chunk': '', 'done': True, 'full_response': format_response(full_response)})}\n\n"
    
    return app.response_class(generate(), mimetype='text/event-stream')

# Regular chat endpoint (non-streaming)
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    session_id = data.get('session_id')
    user_message = data.get('message', '').strip()
    
    if not session_id or session_id not in chat_sessions:
        return jsonify({'error': 'Invalid session'}), 400
    
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    
    # Add user message to memory
    chat_sessions[session_id]['memory'].append({'role': 'user', 'content': user_message})
    
    try:
        ai_reply = ask_ai(chat_sessions[session_id]['memory'])
        formatted_reply = format_response(ai_reply)
        chat_sessions[session_id]['memory'].append({'role': 'assistant', 'content': ai_reply})
        return jsonify({'reply': formatted_reply, 'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Get chat history
@app.route('/api/history/<session_id>')
def get_history(session_id):
    if session_id in chat_sessions:
        return jsonify({
            'memory': chat_sessions[session_id]['memory'],
            'files': chat_sessions[session_id]['files'],
            'created_at': chat_sessions[session_id]['created_at']
        })
    return jsonify({'error': 'Session not found'}), 404

# Export chat as text
@app.route('/api/export/<session_id>')
def export_chat(session_id):
    if session_id not in chat_sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    chat_text = f"AI Chat Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    chat_text += "="*50 + "\n\n"
    
    for message in chat_sessions[session_id]['memory']:
        role = "You" if message['role'] == 'user' else "AI"
        chat_text += f"{role}:\n{message['content']}\n\n"
    
    return jsonify({'chat_text': chat_text})

# Clean old sessions (cron job for production)
@app.route('/api/cleanup', methods=['POST'])
def cleanup_sessions():
    now = datetime.now()
    expired_sessions = []
    
    for session_id, session_data in list(chat_sessions.items()):
        created_at = datetime.fromisoformat(session_data['created_at'])
        if (now - created_at).total_seconds() > 3600:  # 1 hour expiry
            expired_sessions.append(session_id)
            del chat_sessions[session_id]
    
    return jsonify({'cleaned': len(expired_sessions), 'remaining': len(chat_sessions)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting Pro AI Chat Server on port {port}...")
    print(f"📱 Access at: http://localhost:{port}")
    print(f"🔑 Using API Key: {'Set' if OPENROUTER_API_KEY else 'Not Set'}")
    print("💡 Features: Streaming, File Uploads, Session Management")
    app.run(host='0.0.0.0', port=port, debug=False)
