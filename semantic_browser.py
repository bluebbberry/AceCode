#!/usr/bin/env python3
"""
ACE Semantic Rules Desktop IDE
A desktop application for editing ACE rules, facts, and executing queries
IntelliJ-style layout with file explorer, main editor, and results panel
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, Menu
import sqlite3
import re
from datetime import datetime, date
from typing import Dict, List, Any, Tuple
import json
import os
import threading
from pathlib import Path


# Simple Prolog-like inference engine (same as web version)
class PrologEngine:
    def __init__(self):
        self.facts = {}
        self.rules = []
        self.execution_trace = []

    def clear(self):
        """Clear all facts and rules"""
        self.facts = {}
        self.rules = []
        self.execution_trace = []

    def add_fact(self, predicate: str, *args):
        if predicate not in self.facts:
            self.facts[predicate] = []
        self.facts[predicate].append(args)
        self.execution_trace.append(f"Added fact: {predicate}({', '.join(map(str, args))})")

    def add_rule(self, head: Tuple[str, tuple], body: List[Tuple[str, tuple]]):
        self.rules.append((head, body))
        head_str = f"{head[0]}({', '.join(map(str, head[1]))})"
        body_str = " AND ".join([f"{b[0]}({', '.join(map(str, b[1]))})" for b in body])
        self.execution_trace.append(f"Added rule: {head_str} :- {body_str}")

    def query(self, predicate: str, *args) -> List[Dict]:
        self.execution_trace.append(f"Query: {predicate}({', '.join(map(str, args))})")
        results = []

        # Check facts first
        if predicate in self.facts:
            for fact_args in self.facts[predicate]:
                bindings = self._try_unify(args, fact_args)
                if bindings is not None:
                    results.append({'bindings': bindings})

        # Check rules
        for i, (head, body) in enumerate(self.rules):
            head_pred, head_args = head
            if head_pred == predicate:
                bindings = self._try_unify(args, head_args)
                if bindings is not None:
                    if self._evaluate_body_with_bindings(body, bindings):
                        results.append({'bindings': bindings})

        return results

    def _try_unify(self, pattern, fact):
        if len(pattern) != len(fact):
            return None

        bindings = {}
        for i, (p, f) in enumerate(zip(pattern, fact)):
            if isinstance(f, str) and f.startswith('_'):
                if f in bindings:
                    if bindings[f] != p:
                        return None
                else:
                    bindings[f] = p
            elif isinstance(p, str) and p.startswith('_'):
                if p in bindings:
                    if bindings[p] != f:
                        return None
                else:
                    bindings[p] = f
            elif p != f:
                return None

        return bindings

    def _evaluate_body_with_bindings(self, body: List[Tuple[str, tuple]], bindings: Dict) -> bool:
        for i, (pred, args) in enumerate(body):
            substituted_args = []
            for arg in args:
                if isinstance(arg, str) and arg.startswith('_') and arg in bindings:
                    substituted_args.append(bindings[arg])
                else:
                    substituted_args.append(arg)

            if pred == "age_less_than":
                person, age_limit = substituted_args
                actual_age = self._calculate_age(person)
                if actual_age >= age_limit:
                    return False
            elif pred == "income_less_than":
                person, income_limit = substituted_args
                if 'yearly_income' in self.facts:
                    income_found = False
                    for fact_args in self.facts['yearly_income']:
                        if fact_args[0] == person:
                            actual_income = fact_args[1]
                            if actual_income >= income_limit:
                                return False
                            income_found = True
                            break
                    if not income_found:
                        return False
                else:
                    return False
            elif pred == "has_child_under_18":
                person = substituted_args[0]
                if 'has_child' in self.facts:
                    has_child_under_18 = False
                    for parent, child in self.facts['has_child']:
                        if parent == person:
                            child_age = self._calculate_age(child)
                            if child_age < 18:
                                has_child_under_18 = True
                                break
                    if not has_child_under_18:
                        return False
                else:
                    return False
            else:
                sub_results = self.query(pred, *substituted_args)
                if not sub_results:
                    return False

        return True

    def _calculate_age(self, person: str) -> int:
        if 'birthdate' in self.facts:
            for fact_args in self.facts['birthdate']:
                if fact_args[0] == person:
                    birth_year, birth_month, birth_day = fact_args[1:4]
                    today = date.today()
                    age = today.year - birth_year
                    if today.month < birth_month or (today.month == birth_month and today.day < birth_day):
                        age -= 1
                    return age
        return 0


class SemanticBrowser:
    def __init__(self, db_path: str = "family_data.db"):
        self.db_path = db_path
        self.prolog = PrologEngine()
        self._setup_test_db()

        # Default ACE rule sets
        self.default_rules = {
            "kindergeld": """If a person has children 
and the person's yearly_income is below 68000 euros
and at least one child is younger than 18 years
and the person has tax_residence in Germany
then the person is eligible for Kindergeld.

If a person is eligible for Kindergeld 
and the person has 1 child
then the kindergeld_amount is 250 euros per month.

If a person is eligible for Kindergeld 
and the person has 2 children
then the kindergeld_amount is 500 euros per month.""",

            "tax_benefits": """If a person's yearly_income is below 30000 euros
and the person has tax_residence in Germany
then the person is eligible for low_income_tax_relief.

If a person is eligible for low_income_tax_relief
and the person has children
then the person gets additional_family_tax_benefits.""",

            "student_support": """If a person is a student
and the person is younger than 25 years
and the person's parents yearly_income is below 50000 euros
then the person is eligible for student_support."""
        }

    def _setup_test_db(self):
        """Setup test database with sample data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DROP TABLE IF EXISTS children")
        cursor.execute("DROP TABLE IF EXISTS persons")

        cursor.execute("""
            CREATE TABLE persons (
                id INTEGER PRIMARY KEY,
                name TEXT,
                annual_gross_income INTEGER,
                tax_residence_country TEXT,
                age INTEGER,
                is_student INTEGER,
                studies_full_time INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE children (
                id INTEGER PRIMARY KEY,
                parent_id INTEGER,
                birth_year INTEGER,
                birth_month INTEGER,
                birth_day INTEGER,
                FOREIGN KEY (parent_id) REFERENCES persons (id)
            )
        """)

        # Insert test data
        test_persons = [
            (12345, 'Maria Schmidt', 45000, 'Germany', 35, 0, 0),
            (12346, 'Hans Mueller', 25000, 'Germany', 28, 0, 0),
            (12347, 'Anna Weber', 75000, 'Germany', 42, 0, 0),
            (12348, 'Peter Jung', 15000, 'Austria', 22, 1, 1),
            (12349, 'Lisa Klein', 0, 'Germany', 20, 1, 1)
        ]

        cursor.executemany("""
            INSERT INTO persons (id, name, annual_gross_income, tax_residence_country, age, is_student, studies_full_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, test_persons)

        # Children data
        test_children = [
            (67890, 12345, 2010, 3, 15),  # Maria's children
            (67891, 12345, 2018, 7, 22),
            (67892, 12346, 2015, 12, 1),  # Hans's child
            (67893, 12347, 2008, 5, 10),  # Anna's children
            (67894, 12347, 2020, 9, 3),
        ]

        cursor.executemany("""
            INSERT INTO children (id, parent_id, birth_year, birth_month, birth_day)
            VALUES (?, ?, ?, ?, ?)
        """, test_children)

        conn.commit()
        conn.close()

    def sql_to_ace(self) -> List[str]:
        """Convert database data to ACE facts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM persons")
        persons = cursor.fetchall()

        cursor.execute("SELECT * FROM children")
        children = cursor.fetchall()

        conn.close()

        ace_facts = []

        # Convert persons to ACE
        for person in persons:
            person_id, name, income, country, age, is_student, studies_full_time = person
            person_ace = name.replace(' ', '_').lower()

            ace_facts.append(f"{person_ace} is a person.")
            if income:
                ace_facts.append(f"{person_ace} has a yearly_income of {income} euros.")
            if country:
                ace_facts.append(f"{person_ace} has tax_residence in {country}.")
            if age:
                ace_facts.append(f"{person_ace} has age {age} years.")
            if is_student:
                ace_facts.append(f"{person_ace} is a student.")
            if studies_full_time:
                ace_facts.append(f"{person_ace} studies full_time.")

        # Convert children to ACE
        for child in children:
            child_id, parent_id, birth_year, birth_month, birth_day = child
            child_ace = f"child_{child_id}"

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM persons WHERE id = ?", (parent_id,))
            parent_name = cursor.fetchone()[0].replace(' ', '_').lower()
            conn.close()

            ace_facts.append(f"{child_ace} is a child.")
            ace_facts.append(f"{parent_name} has child {child_ace}.")
            ace_facts.append(f"{child_ace} has a birthdate of {birth_year}-{birth_month:02d}-{birth_day:02d}.")

        return ace_facts

    def parse_ace_rules_with_custom_facts(self, ace_rules: str, custom_facts: str = ""):
        """Parse ACE rules and add to Prolog"""
        self.prolog.clear()

        # Load facts
        if custom_facts.strip():
            fact_lines = [line.strip() for line in custom_facts.split('\n') if line.strip()]
            for fact in fact_lines:
                self._parse_ace_fact(fact)
        else:
            ace_facts = self.sql_to_ace()
            for fact in ace_facts:
                self._parse_ace_fact(fact)

        # Parse and add rules
        if "kindergeld" in ace_rules.lower() or "If a person has children" in ace_rules:
            self._add_kindergeld_rules()
        if "tax_relief" in ace_rules.lower() or "low_income_tax_relief" in ace_rules.lower():
            self._add_tax_relief_rules()
        if "student_support" in ace_rules.lower():
            self._add_student_support_rules()

    def _parse_ace_fact(self, ace_fact: str):
        """Parse ACE fact and add to Prolog"""
        ace_fact = ace_fact.strip('.')

        if " is a " in ace_fact:
            parts = ace_fact.split(" is a ")
            self.prolog.add_fact(parts[1], parts[0])
        elif " has a yearly_income of " in ace_fact:
            match = re.search(r"(\w+) has a yearly_income of (\d+) euros", ace_fact)
            if match:
                self.prolog.add_fact("yearly_income", match.group(1), int(match.group(2)))
        elif " has tax_residence in " in ace_fact:
            match = re.search(r"(\w+) has tax_residence in (\w+)", ace_fact)
            if match:
                self.prolog.add_fact("tax_residence", match.group(1), match.group(2).lower())
        elif " has child " in ace_fact:
            match = re.search(r"(\w+) has child (\w+)", ace_fact)
            if match:
                self.prolog.add_fact("has_child", match.group(1), match.group(2))
        elif " has a birthdate of " in ace_fact:
            match = re.search(r"(\w+) has a birthdate of (\d{4})-(\d{2})-(\d{2})", ace_fact)
            if match:
                self.prolog.add_fact("birthdate", match.group(1),
                                     int(match.group(2)), int(match.group(3)), int(match.group(4)))

    def _add_kindergeld_rules(self):
        """Add Kindergeld rules"""
        self.prolog.add_rule(
            ("eligible_for_kindergeld", ("_person",)),
            [
                ("person", ("_person",)),
                ("has_child", ("_person", "_child")),
                ("income_less_than", ("_person", 68000)),
                ("has_child_under_18", ("_person",)),
                ("tax_residence", ("_person", "germany"))
            ]
        )

    def _add_tax_relief_rules(self):
        """Add tax relief rules"""
        self.prolog.add_rule(
            ("eligible_for_low_income_tax_relief", ("_person",)),
            [
                ("person", ("_person",)),
                ("income_less_than", ("_person", 30000)),
                ("tax_residence", ("_person", "germany"))
            ]
        )

    def _add_student_support_rules(self):
        """Add student support rules"""
        self.prolog.add_rule(
            ("eligible_for_student_support", ("_person",)),
            [
                ("student", ("_person",)),
                ("age_less_than", ("_person", 25))
            ]
        )

    def execute_query(self, ace_rules: str, query: str, custom_facts: str = ""):
        """Execute a query and return results"""
        try:
            # Parse rules and setup knowledge base
            self.parse_ace_rules_with_custom_facts(ace_rules, custom_facts)

            # Parse query
            query_lower = query.lower().strip('?').strip()
            query_parts = query_lower.split()

            results = []
            answer = ""

            if query_lower.startswith("is ") and len(query_parts) >= 2:
                person = query_parts[1]

                if "eligible" in query_lower:
                    if "kindergeld" in query_lower:
                        query_results = self.prolog.query("eligible_for_kindergeld", person)
                        if query_results:
                            answer = f"Yes, {person} is eligible for Kindergeld."
                            results = [{"result": "eligible", "person": person, "benefit": "Kindergeld"}]
                        else:
                            answer = f"No, {person} is not eligible for Kindergeld."
                    elif "tax_relief" in query_lower:
                        query_results = self.prolog.query("eligible_for_low_income_tax_relief", person)
                        if query_results:
                            answer = f"Yes, {person} is eligible for low income tax relief."
                        else:
                            answer = f"No, {person} is not eligible for low income tax relief."

            elif query_lower.startswith("who "):
                if "eligible" in query_lower and "kindergeld" in query_lower:
                    persons = self.prolog.facts.get("person", [])
                    eligible_persons = []
                    for (person,) in persons:
                        if self.prolog.query("eligible_for_kindergeld", person):
                            eligible_persons.append(person)

                    if eligible_persons:
                        answer = f"Eligible for Kindergeld: {', '.join(eligible_persons)}"
                        results = [{"person": person, "benefit": "Kindergeld"} for person in eligible_persons]
                    else:
                        answer = "No one is eligible for Kindergeld."

                elif "children" in query_lower:
                    if "has_child" in self.prolog.facts:
                        parents = list(set([parent for parent, child in self.prolog.facts["has_child"]]))
                        if parents:
                            answer = f"People with children: {', '.join(parents)}"
                            results = [{"person": parent, "has": "children"} for parent in parents]
                        else:
                            answer = "No one has children."

            if not answer:
                answer = "I couldn't parse that query. Please try one of the example queries."

            return {
                'success': True,
                'results': results,
                'answer': answer,
                'execution_trace': self.prolog.execution_trace,
                'facts_count': sum(len(facts) for facts in self.prolog.facts.values()),
                'rules_count': len(self.prolog.rules)
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'execution_trace': self.prolog.execution_trace if hasattr(self, 'prolog') else []
            }


class ACEIDE:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ACE Semantic Rules IDE")
        self.root.geometry("1400x900")

        # Cross-platform window maximization
        try:
            self.root.state('zoomed')  # Windows
        except tk.TclError:
            try:
                # Linux/Unix - use attributes to maximize
                self.root.attributes('-zoomed', True)
            except tk.TclError:
                # Fallback: get screen dimensions and set window size
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                self.root.geometry(f"{screen_width - 100}x{screen_height - 100}+50+50")

        # Initialize semantic browser
        self.browser = SemanticBrowser()

        # File and project management
        self.current_file = None
        self.is_modified = False
        self.workspace_path = os.path.expanduser("~/ACE_Workspace")
        self.create_default_workspace()

        # Current document content
        self.current_doc_type = None  # 'rules', 'facts', 'query'

        # Create the interface
        self.create_menu()
        self.create_interface()
        self.load_default_content()

        # Bind events
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_default_workspace(self):
        """Create default workspace with sample files"""
        if not os.path.exists(self.workspace_path):
            os.makedirs(self.workspace_path)

        # Create sample files if they don't exist
        sample_files = {
            "kindergeld_rules.ace": self.browser.default_rules["kindergeld"],
            "tax_benefits.ace": self.browser.default_rules["tax_benefits"],
            "student_support.ace": self.browser.default_rules["student_support"],
            "sample_facts.ace": "\n".join(self.browser.sql_to_ace()),
            "sample_query.ace": "Is maria_schmidt eligible for Kindergeld?"
        }

        for filename, content in sample_files.items():
            filepath = os.path.join(self.workspace_path, filename)
            if not os.path.exists(filepath):
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)

    def create_menu(self):
        """Create menu bar"""
        menubar = Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New File", command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Open File", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As", command=self.save_as_file, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Refresh Explorer", command=self.refresh_explorer, accelerator="F5")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)

        # Run menu
        run_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Run", menu=run_menu)
        run_menu.add_command(label="Execute Query", command=self.execute_current_query, accelerator="Ctrl+Enter")

        # View menu
        view_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Toggle Explorer", command=self.toggle_explorer)

        # Keyboard shortcuts
        self.root.bind('<Control-n>', lambda e: self.new_file())
        self.root.bind('<Control-o>', lambda e: self.open_file())
        self.root.bind('<Control-s>', lambda e: self.save_file())
        self.root.bind('<Control-Shift-S>', lambda e: self.save_as_file())
        self.root.bind('<F5>', lambda e: self.refresh_explorer())
        self.root.bind('<Control-Return>', lambda e: self.execute_current_query())

    def create_interface(self):
        """Create the IntelliJ-style interface"""
        # Main container with three panels
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Left panel: File Explorer
        self.create_file_explorer(main_paned)

        # Right panel: Editor + Results
        right_paned = ttk.PanedWindow(main_paned, orient=tk.VERTICAL)
        main_paned.add(right_paned, weight=4)

        # Top right: Editor with toolbar
        self.create_editor_panel(right_paned)

        # Bottom right: Results panel
        self.create_results_panel(right_paned)

        # Status bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def create_file_explorer(self, parent):
        """Create file explorer panel"""
        self.explorer_frame = ttk.Frame(parent)
        parent.add(self.explorer_frame, weight=1)

        # Explorer header
        explorer_header = ttk.Frame(self.explorer_frame)
        explorer_header.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(explorer_header, text="📁 Project Explorer", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        ttk.Button(explorer_header, text="⟳", width=3, command=self.refresh_explorer).pack(side=tk.RIGHT)

        # File tree
        tree_frame = ttk.Frame(self.explorer_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)

        self.file_tree = ttk.Treeview(tree_frame, height=15)
        self.file_tree.pack(fill=tk.BOTH, expand=True)

        # Bind file selection
        self.file_tree.bind('<Double-1>', self.on_file_double_click)
        self.file_tree.bind('<Button-3>', self.on_file_right_click)  # Right click menu

        # Context menu for files
        self.file_context_menu = Menu(self.root, tearoff=0)
        self.file_context_menu.add_command(label="Open", command=self.open_selected_file)
        self.file_context_menu.add_command(label="Delete", command=self.delete_selected_file)
        self.file_context_menu.add_command(label="Rename", command=self.rename_selected_file)

        self.refresh_explorer()

    def create_editor_panel(self, parent):
        """Create main editor panel"""
        editor_frame = ttk.Frame(parent)
        parent.add(editor_frame, weight=3)

        # Editor toolbar
        toolbar = ttk.Frame(editor_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=2)

        # File info label
        self.file_label = ttk.Label(toolbar, text="No file open", font=("Segoe UI", 10))
        self.file_label.pack(side=tk.LEFT)

        # Execute button
        self.execute_btn = ttk.Button(toolbar, text="▶ Execute", command=self.execute_current_query)
        self.execute_btn.pack(side=tk.RIGHT, padx=5)
        self.execute_btn.config(state='disabled')

        # Document type indicator
        self.doc_type_label = ttk.Label(toolbar, text="", font=("Segoe UI", 9))
        self.doc_type_label.pack(side=tk.RIGHT, padx=10)

        # Main editor
        self.editor = scrolledtext.ScrolledText(
            editor_frame,
            wrap=tk.WORD,
            font=("Consolas", 12),
            bg="#2d3748",
            fg="#e2e8f0",
            insertbackground="white",
            selectbackground="#4a5568",
            relief=tk.FLAT,
            borderwidth=0
        )
        self.editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.editor.bind('<KeyRelease>', self.on_text_change)

    def create_results_panel(self, parent):
        """Create results panel at bottom"""
        results_frame = ttk.LabelFrame(parent, text="🔍 Query Results")
        parent.add(results_frame, weight=1)

        # Results notebook for different views
        self.results_notebook = ttk.Notebook(results_frame)
        self.results_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Answer tab
        answer_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(answer_frame, text="Answer")

        self.answer_text = scrolledtext.ScrolledText(
            answer_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg="#f7fafc",
            fg="#2d3748",
            height=8
        )
        self.answer_text.pack(fill=tk.BOTH, expand=True)

        # Execution trace tab
        trace_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(trace_frame, text="Trace")

        self.trace_text = scrolledtext.ScrolledText(
            trace_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#1a202c",
            fg="#68d391",
            height=8
        )
        self.trace_text.pack(fill=tk.BOTH, expand=True)

        # Knowledge base tab
        kb_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(kb_frame, text="Knowledge Base")

        self.kb_text = scrolledtext.ScrolledText(
            kb_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#fdf6e3",
            fg="#657b83",
            height=8
        )
        self.kb_text.pack(fill=tk.BOTH, expand=True)

    def refresh_explorer(self):
        """Refresh the file explorer"""
        # Clear existing items
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)

        # Add workspace folder
        if os.path.exists(self.workspace_path):
            workspace_name = os.path.basename(self.workspace_path)
            workspace_item = self.file_tree.insert('', 'end', text=f"📁 {workspace_name}",
                                                   values=(self.workspace_path,), open=True)

            # Add files
            try:
                for filename in sorted(os.listdir(self.workspace_path)):
                    filepath = os.path.join(self.workspace_path, filename)
                    if os.path.isfile(filepath):
                        # Determine file icon based on extension or content
                        if filename.endswith('.ace'):
                            # Try to determine type from content
                            try:
                                with open(filepath, 'r', encoding='utf-8') as f:
                                    content = f.read().lower()
                                    if 'if ' in content and 'then ' in content:
                                        icon = "📋"  # Rules
                                    elif any(line.endswith('.') and ' is a ' in line for line in content.split('\n')):
                                        icon = "📝"  # Facts
                                    elif '?' in content:
                                        icon = "❓"  # Query
                                    else:
                                        icon = "📄"  # Generic ACE file
                            except:
                                icon = "📄"
                        else:
                            icon = "📄"

                        self.file_tree.insert(workspace_item, 'end', text=f"{icon} {filename}",
                                              values=(filepath,))
            except PermissionError:
                pass

    def on_file_double_click(self, event):
        """Handle file double click"""
        self.open_selected_file()

    def on_file_right_click(self, event):
        """Handle file right click"""
        item = self.file_tree.selection()[0] if self.file_tree.selection() else None
        if item and self.file_tree.item(item, 'values'):
            self.file_context_menu.post(event.x_root, event.y_root)

    def open_selected_file(self):
        """Open the selected file in explorer"""
        item = self.file_tree.selection()[0] if self.file_tree.selection() else None
        if item:
            values = self.file_tree.item(item, 'values')
            if values:
                filepath = values[0]
                if os.path.isfile(filepath):
                    self.open_file_by_path(filepath)

    def delete_selected_file(self):
        """Delete the selected file"""
        item = self.file_tree.selection()[0] if self.file_tree.selection() else None
        if item:
            values = self.file_tree.item(item, 'values')
            if values:
                filepath = values[0]
                if os.path.isfile(filepath):
                    if messagebox.askyesno("Delete File",
                                           f"Are you sure you want to delete {os.path.basename(filepath)}?"):
                        os.remove(filepath)
                        self.refresh_explorer()

    def rename_selected_file(self):
        """Rename the selected file"""
        # Simple implementation - could be enhanced with inline editing
        item = self.file_tree.selection()[0] if self.file_tree.selection() else None
        if item:
            values = self.file_tree.item(item, 'values')
            if values:
                old_filepath = values[0]
                if os.path.isfile(old_filepath):
                    old_filename = os.path.basename(old_filepath)
                    # Import simpledialog for rename functionality
                    import tkinter.simpledialog
                    new_filename = tkinter.simpledialog.askstring("Rename File", "New filename:", initialvalue=old_filename)
                    if new_filename and new_filename != old_filename:
                        new_filepath = os.path.join(os.path.dirname(old_filepath), new_filename)
                        os.rename(old_filepath, new_filepath)
                        self.refresh_explorer()

    def open_file_by_path(self, filepath):
        """Open a file by its path"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Clear editor and load content
            self.editor.delete('1.0', tk.END)
            self.editor.insert('1.0', content)

            # Update current file info
            self.current_file = filepath
            filename = os.path.basename(filepath)
            self.file_label.config(text=filename)

            # Determine document type and enable/disable execute button
            content_lower = content.lower()
            if '?' in content_lower and len(content.strip().split('\n')) <= 5:  # Likely a query
                self.current_doc_type = 'query'
                self.doc_type_label.config(text="🔍 Query", foreground="blue")
                self.execute_btn.config(state='normal')
            elif 'if ' in content_lower and 'then ' in content_lower:
                self.current_doc_type = 'rules'
                self.doc_type_label.config(text="📋 Rules", foreground="green")
                self.execute_btn.config(state='disabled')
            elif any(line.endswith('.') and ' is a ' in line for line in content.split('\n')):
                self.current_doc_type = 'facts'
                self.doc_type_label.config(text="📝 Facts", foreground="orange")
                self.execute_btn.config(state='disabled')
            else:
                self.current_doc_type = 'unknown'
                self.doc_type_label.config(text="📄 Document", foreground="gray")
                self.execute_btn.config(state='disabled')

            self.is_modified = False
            self.update_title()
            self.status_bar.config(text=f"Opened: {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Could not open file:\n{str(e)}")

    def load_default_content(self):
        """Load default content on startup"""
        # Open the sample query file by default
        query_file = os.path.join(self.workspace_path, "sample_query.ace")
        if os.path.exists(query_file):
            self.open_file_by_path(query_file)

    def on_text_change(self, event=None):
        """Handle text changes in editor"""
        self.is_modified = True
        self.update_title()

    def update_title(self):
        """Update window title"""
        title = "ACE Semantic Rules IDE"
        if self.current_file:
            filename = os.path.basename(self.current_file)
            title += f" - {filename}"
        if self.is_modified:
            title += " *"
        self.root.title(title)

    def new_file(self):
        """Create a new file"""
        if self.is_modified:
            result = messagebox.askyesnocancel("Unsaved Changes",
                                               "Save current file before creating new one?")
            if result is True:  # Save
                self.save_file()
            elif result is None:  # Cancel
                return

        # Ask for filename and type
        filename = filedialog.asksaveasfilename(
            title="New ACE File",
            defaultextension=".ace",
            filetypes=[("ACE files", "*.ace"), ("All files", "*.*")],
            initialdir=self.workspace_path
        )

        if filename:
            # Create empty file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("")

            # Open it
            self.open_file_by_path(filename)
            self.refresh_explorer()

    def open_file(self):
        """Open file dialog"""
        filename = filedialog.askopenfilename(
            title="Open ACE File",
            filetypes=[("ACE files", "*.ace"), ("All files", "*.*")],
            initialdir=self.workspace_path
        )

        if filename:
            self.open_file_by_path(filename)

    def save_file(self):
        """Save current file"""
        if self.current_file:
            try:
                content = self.editor.get('1.0', tk.END).strip()
                with open(self.current_file, 'w', encoding='utf-8') as f:
                    f.write(content)

                self.is_modified = False
                self.update_title()
                filename = os.path.basename(self.current_file)
                self.status_bar.config(text=f"Saved: {filename}")
                self.refresh_explorer()  # Refresh to update file icons

            except Exception as e:
                messagebox.showerror("Error", f"Could not save file:\n{str(e)}")
        else:
            self.save_as_file()

    def save_as_file(self):
        """Save as new file"""
        filename = filedialog.asksaveasfilename(
            title="Save ACE File",
            defaultextension=".ace",
            filetypes=[("ACE files", "*.ace"), ("All files", "*.*")],
            initialdir=self.workspace_path
        )

        if filename:
            try:
                content = self.editor.get('1.0', tk.END).strip()
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)

                self.current_file = filename
                self.is_modified = False
                self.update_title()
                self.file_label.config(text=os.path.basename(filename))
                self.status_bar.config(text=f"Saved: {os.path.basename(filename)}")
                self.refresh_explorer()

            except Exception as e:
                messagebox.showerror("Error", f"Could not save file:\n{str(e)}")

    def execute_current_query(self):
        """Execute the current query"""
        if self.current_doc_type != 'query':
            messagebox.showinfo("Info",
                                "Please open a query file to execute.\nQuery files should contain questions like 'Is maria_schmidt eligible for Kindergeld?'")
            return

        # Get query content
        query = self.editor.get('1.0', tk.END).strip()
        if not query:
            messagebox.showwarning("Warning", "Please enter a query")
            return

        # Update status
        self.status_bar.config(text="Executing query...")
        self.root.update()

        # Clear previous results
        self.answer_text.delete('1.0', tk.END)
        self.trace_text.delete('1.0', tk.END)
        self.kb_text.delete('1.0', tk.END)

        # Find rules and facts files in workspace
        rules_content = ""
        facts_content = ""

        # Look for rules and facts files
        for filename in os.listdir(self.workspace_path):
            filepath = os.path.join(self.workspace_path, filename)
            if os.path.isfile(filepath) and filename.endswith('.ace'):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        content_lower = content.lower()

                        if 'if ' in content_lower and 'then ' in content_lower:
                            rules_content += content + "\n\n"
                        elif any(line.endswith('.') and ' is a ' in line for line in content.split('\n')):
                            facts_content += content + "\n\n"
                except:
                    pass

        # Execute in separate thread
        def execute_thread():
            try:
                result = self.browser.execute_query(rules_content.strip(), query, facts_content.strip())
                self.root.after(0, lambda: self.display_results(result))
            except Exception as e:
                error_result = {
                    'success': False,
                    'error': str(e),
                    'execution_trace': []
                }
                self.root.after(0, lambda: self.display_results(error_result))

        thread = threading.Thread(target=execute_thread)
        thread.daemon = True
        thread.start()

    def display_results(self, result):
        """Display query results"""
        if result['success']:
            # Display answer
            answer = result.get('answer', 'No answer provided')
            self.answer_text.insert('1.0', f"✅ SUCCESS\n\n")
            self.answer_text.insert(tk.END, f"📋 Answer:\n{answer}\n\n")

            # Display structured results
            if result.get('results'):
                self.answer_text.insert(tk.END, f"📊 Detailed Results:\n")
                self.answer_text.insert(tk.END, json.dumps(result['results'], indent=2))
                self.answer_text.insert(tk.END, "\n\n")

            # Display knowledge base stats
            facts_count = result.get('facts_count', 0)
            rules_count = result.get('rules_count', 0)
            self.answer_text.insert(tk.END, f"🧠 Knowledge Base: {facts_count} facts | {rules_count} rules")

            # Style success message
            self.answer_text.tag_add("success", "1.0", "1.end")
            self.answer_text.tag_config("success", foreground="green", font=("Segoe UI", 11, "bold"))

            self.status_bar.config(text="✅ Query executed successfully")

        else:
            # Display error
            error_msg = result.get('error', 'Unknown error')
            self.answer_text.insert('1.0', f"❌ ERROR\n\n")
            self.answer_text.insert(tk.END, f"Error Details:\n{error_msg}")

            # Style error message
            self.answer_text.tag_add("error", "1.0", "1.end")
            self.answer_text.tag_config("error", foreground="red", font=("Segoe UI", 11, "bold"))

            self.status_bar.config(text="❌ Query execution failed")

        # Display execution trace
        if result.get('execution_trace'):
            trace_text = "\n".join(result['execution_trace'])
            self.trace_text.insert('1.0', trace_text)

        # Display knowledge base info
        if result.get('success'):
            kb_info = f"Facts loaded:\n"
            if hasattr(self.browser.prolog, 'facts'):
                for predicate, facts_list in self.browser.prolog.facts.items():
                    kb_info += f"  {predicate}: {len(facts_list)} entries\n"

            kb_info += f"\nRules loaded:\n"
            if hasattr(self.browser.prolog, 'rules'):
                for i, (head, body) in enumerate(self.browser.prolog.rules):
                    kb_info += f"  Rule {i + 1}: {head[0]}\n"

            self.kb_text.insert('1.0', kb_info)

        # Switch to answer tab and show results
        self.results_notebook.select(0)

    def toggle_explorer(self):
        """Toggle file explorer visibility"""
        # This could be enhanced to actually hide/show the explorer
        self.refresh_explorer()

    def on_closing(self):
        """Handle application closing"""
        if self.is_modified:
            result = messagebox.askyesnocancel("Unsaved Changes",
                                               "Save current file before closing?")
            if result is True:  # Save
                self.save_file()
            elif result is None:  # Cancel
                return

        self.root.destroy()

    def run(self):
        """Start the IDE"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.root.destroy()


def main():
    """Main entry point"""
    try:
        # Create and run the IDE
        ide = ACEIDE()

        print("🚀 Starting ACE Semantic Rules Desktop IDE...")
        print("📊 Database initialized with sample data")
        print(f"📁 Workspace created at: {ide.workspace_path}")
        print("💡 Double-click files in explorer to open them")
        print("🔍 Open query files and press Ctrl+Enter to execute")
        print("📋 Create rules files with 'If...then...' statements")
        print("📝 Create facts files with 'person is a...' statements")

        ide.run()

    except Exception as e:
        print(f"Error starting IDE: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()