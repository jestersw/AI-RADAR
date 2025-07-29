from flask import Flask, request, jsonify
import hmac
import hashlib
import os
import logging
from datetime import datetime
from git_analyzer import GitAnalyzer
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

# Логирование
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)
logger = logging.getLogger(__name__)

# Метрики простым способом
webhook_metrics = {
    'total_requests': 0,
    'successful_requests': 0,
    'failed_requests': 0,
    'dependency_changes_detected': 0
}

app = Flask(__name__)

def verify_github_signature(payload_body, signature_header):
    if not signature_header:
        return False
    hash_object = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)

@app.route('/webhook/github', methods=['POST'])
def github_webhook():
    webhook_metrics['total_requests'] += 1
    payload_body = request.data
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_github_signature(payload_body, signature):
        webhook_metrics['failed_requests'] += 1
        logger.warning('Invalid signature')
        return jsonify({'error': 'Invalid signature'}), 403
    
    payload = request.json
    event_type = request.headers.get('X-GitHub-Event')
    analyzer = GitAnalyzer()
    try:
        if event_type == 'push':
            results = analyzer.handle_push_event(payload)
        elif event_type == 'pull_request':
            results = analyzer.handle_pr_event(payload)
        else:
            return jsonify({'message': 'Event type not supported'}), 200
        logger.info(f"Processed {event_type} event: {results}")
        webhook_metrics['successful_requests'] += 1
        # Считаем сколько коммитов с изменением зависимостей
        dep_cnt = sum(1 for r in results if r['dependency_changes'])
        webhook_metrics['dependency_changes_detected'] += dep_cnt
        return jsonify({'status': 'success', 'results': results}), 200
    except Exception as e:
        webhook_metrics['failed_requests'] += 1
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({'error': 'Processing failed'}), 500

@app.route('/metrics')
def metrics():
    return jsonify(webhook_metrics)

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
