import json
import re

class DependencyParser:
    def parse_changes(self, file_path: str, old_content: str, new_content: str):
        if file_path.endswith('package.json'):
            return self.parse_package_json_changes(old_content, new_content)
        elif file_path.endswith('requirements.txt'):
            return self.parse_requirements_txt_changes(old_content, new_content)
        # Можно добавить поддержку других форматов ниже (pipfile,...)
        return []

    def parse_package_json_changes(self, old_content, new_content):
        try:
            old_data = json.loads(old_content) if old_content else {}
            new_data = json.loads(new_content) if new_content else {}
            old_deps = {**old_data.get('dependencies', {}), **old_data.get('devDependencies', {})}
            new_deps = {**new_data.get('dependencies', {}), **new_data.get('devDependencies', {})}
            changes = []
            for dep, version in new_deps.items():
                if dep not in old_deps:
                    changes.append({
                        'action': 'added',
                        'package': dep,
                        'new_version': version
                    })
                elif old_deps[dep] != version:
                    changes.append({
                        'action': 'updated',
                        'package': dep,
                        'old_version': old_deps[dep],
                        'new_version': version
                    })
            for dep in old_deps:
                if dep not in new_deps:
                    changes.append({
                        'action': 'removed',
                        'package': dep,
                        'old_version': old_deps[dep]
                    })
            return changes
        except Exception as e:
            return [{'error': f'Invalid JSON or failed diff: {e}'}]

    def parse_requirements_txt_changes(self, old_content, new_content):
        def parse_requirements(content):
            deps = {}
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    if '==' in line:
                        name, version = line.split('==', 1)
                        deps[name.strip()] = version.strip()
                    elif '>=' in line:
                        name, version = line.split('>=', 1)
                        deps[name.strip()] = f">={version.strip()}"
                    else:
                        # Просто имя пакета, версия неизвестна
                        deps[line] = "latest"
            return deps
        old_deps = parse_requirements(old_content)
        new_deps = parse_requirements(new_content)
        changes = []
        for dep, version in new_deps.items():
            if dep not in old_deps:
                changes.append({
                    'action': 'added',
                    'package': dep,
                    'new_version': version
                })
            elif old_deps[dep] != version:
                changes.append({
                    'action': 'updated',
                    'package': dep,
                    'old_version': old_deps[dep],
                    'new_version': version
                })
        for dep in old_deps:
            if dep not in new_deps:
                changes.append({
                    'action': 'removed',
                    'package': dep,
                    'old_version': old_deps[dep]
                })
        return changes
