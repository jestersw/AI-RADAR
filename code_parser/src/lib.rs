use pyo3::prelude::*;
use pyo3::types::PyDict;
use tree_sitter::{Language, Parser, Node, Query, QueryCursor};

extern "C" {
    fn tree_sitter_python() -> Language;
    fn tree_sitter_javascript() -> Language;
}

#[pyclass]
pub struct CodeAnalyzer {
    parser: Parser,
    language: Language,
    vuln_queries: Vec<Query>,
}

#[pymethods]
impl CodeAnalyzer {
    #[new]
    fn new(lang: &str) -> PyResult<Self> {
        let mut parser = Parser::new();
        let language = match lang {
            "python" => unsafe { tree_sitter_python() },
            "javascript" => unsafe { tree_sitter_javascript() },
            _ => return Err(pyo3::exceptions::PyValueError::new_err("Unsupported language")),
        };
        parser.set_language(language).map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        // Расширенные запросы для уязвимостей 
        let vuln_queries = vec![
            Query::new(language, "(call function: (identifier) @func) #:match? @func \"^eval$\"")?,  // Insecure eval
            Query::new(language, "(string) @sql #:match? @sql \"SELECT.*FROM.*WHERE\"")?,  // Potential SQL injection
            Query::new(language, "(string) @secret #:match? @secret \"^[A-Za-z0-9+/=]{40,}$\"")?,  // Hardcoded secrets (e.g., API keys)
            Query::new(language, "(call function: (identifier) @rand) #:match? @rand \"^Math.random$\"")?,  // Insecure random in JS
            // Добавь свои: e.g., для XSS, deserialization
        ];

        Ok(CodeAnalyzer { parser, language, vuln_queries })
    }

    fn analyze_file(&mut self, py: Python, content: &str) -> PyResult<PyObject> {
        let tree = match self.parser.parse(content, None) {
            Some(tree) => tree,
            None => return Err(pyo3::exceptions::PyRuntimeError::new_err("Parse failed")),
        };

        let root = tree.root_node();
        let mut cursor = QueryCursor::new();

        // Вычисление метрик
        let complexity = self.calculate_complexity(&root);

        // Поиск уязвимостей с деталями
        let mut vulnerabilities = Vec::new();
        for (i, query) in self.vuln_queries.iter().enumerate() {
            for mat in cursor.matches(query, root, content.as_bytes()) {
                if let Some(capture) = mat.captures.first() {
                    let node = capture.node;
                    let vuln_type = match i {
                        0 => "Insecure eval",
                        1 => "Potential SQL injection",
                        2 => "Hardcoded secret",
                        3 => "Insecure random",
                        _ => "Unknown",
                    };
                    vulnerabilities.push(format!("{} at line {}: {}", vuln_type, node.start_position().row + 1, &content[node.start_byte()..node.end_byte()]));
                }
            }
        }

        let dict = PyDict::new(py);
        dict.set_item("complexity", complexity)?;
        dict.set_item("vulnerabilities", vulnerabilities)?;
        Ok(dict.into())
    }
}

impl CodeAnalyzer {
    fn calculate_complexity(&self, node: &Node) -> u32 {
        let mut count = 1;
        match node.kind() {
            "if_statement" | "for_statement" | "while_statement" | "switch_statement" | "try_statement" => count += 1,
            _ => (),
        }
        for child in node.children(&mut node.walk()) {
            count += self.calculate_complexity(&child);
        }
        count
    }
}

#[pymodule]
fn code_parser(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<CodeAnalyzer>()?;
    Ok(())
}
