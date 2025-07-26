import os
import logging
from typing import Dict, List, Any
from git import Repo
import requests
from requests.exceptions import RequestException
from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from celery import Celery 
from datetime import datetime

# Настройка логирования для аудита
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Celery setup 
app = Celery('data_sources', broker='redis://localhost:6379/0')

# Базовая модель PostgreSQL
Base = declarative_base()
engine = create_engine(os.getenv('DATABASE_URL', 'postgresql://user:pass@localhost/ai_radar'))
Session = sessionmaker(bind=engine)

class DataEntry(Base):
    __tablename__ = 'data_entries'
    id = Column(Integer, primary_key=True)
    source_type = Column(String, nullable=False)  # e.g., 'git', 'snyk'
    data = Column(JSON, nullable=False) 
    timestamp = Column(DateTime, default=datetime.utcnow)
    analyzed = Column(Integer, default=0) 

Base.metadata.create_all(engine)

# Словарь интеграций (расширенный с конфигами)
INTEGRATIONS = {
    'git': {
        'types': ['commits', 'diffs', 'branches'],
        'fetch_func': 'fetch_git_data',
        'config': {'repo_url': 'https://github.com/user/repo.git', 'token': os.getenv('GIT_TOKEN')}
    },
    'ci_cd': {
        'types': ['jenkins', 'gitlab_ci', 'github_actions'],
        'fetch_func': 'fetch_ci_cd_data',
        'config': {'jenkins_url': 'http://jenkins:8080', 'api_key': os.getenv('JENKINS_KEY')}
    },
    'code_quality': {
        'types': ['sonarqube', 'codeclimate'],
        'fetch_func': 'fetch_code_quality_data',
        'config': {'sonarqube_url': 'http://sonarqube:9000', 'token': os.getenv('SONAR_TOKEN')}
    },
    'security_tools': {
        'types': ['snyk', 'checkmarx', 'veracode'],
        'fetch_func': 'fetch_security_data',
        'config': {'snyk_api': 'https://api.snyk.io', 'token': os.getenv('SNYK_TOKEN')}
    },
    'monitoring': {
        'types': ['prometheus', 'grafana', 'elk'],
        'fetch_func': 'fetch_monitoring_data',
        'config': {'prometheus_url': 'http://prometheus:9090'}
    }
}

@app.task
def collect_data(source: str) -> Dict[str, Any]:
    if source not in INTEGRATIONS:
        logger.error(f"Unknown source: {source}")
        return {'status': 'error', 'message': 'Unknown source'}

    config = INTEGRATIONS[source]['config']
    fetch_func = globals()[INTEGRATIONS[source]['fetch_func']]
    
    try:
        data = fetch_func(config)
        if not isinstance(data, list) or not data:
            raise ValueError("Invalid data format")
        
        session = Session()
        for item in data:
            entry = DataEntry(source_type=source, data=item)
            session.add(entry)
        session.commit()
        logger.info(f"Collected {len(data)} items from {source}")
        return {'status': 'success', 'count': len(data)}
    except Exception as e:
        logger.error(f"Error collecting from {source}: {str(e)}")
        return {'status': 'error', 'message': str(e)}

def fetch_git_data(config: Dict) -> List[Dict]:
    repo = Repo.clone_from(config['repo_url'], '/tmp/repo', branch='main')  
    commits = [{'hash': c.hexsha, 'message': c.message, 'diff': c.diff()} for c in repo.iter_commits()]
    return commits[:100] 

def fetch_security_data(config: Dict) -> List[Dict]:
    headers = {'Authorization': f'token {config["token"]}'}
    response = requests.get(f'{config["snyk_api"]}/v1/orgs/org/projects/project/issues', headers=headers)
    response.raise_for_status()
    return response.json().get('issues', []) 

# реализовать в будущем fetch_ci_cd_data, fetch_code_quality_data, fetch_monitoring_data 
  
if __name__ == '__main__':
    for source in INTEGRATIONS:
        collect_data.delay(source) 
