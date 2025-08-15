#!/usr/bin/env python3
"""
Semantic Web Browser Web Frontend - ENHANCED WITH FACT EDITING
Flask-based interface for editing ACE rules, facts, and executing queries
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
import re
from datetime import datetime, date
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
import json
import os

# Import the core semantic web browser logic
import sys

sys.path.append(os.path.dirname(__file__))


# Simple Prolog-like inference engine (FIXED)
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
        self.execution_trace.append(f"Available facts: {list(self.facts.keys())}")
        results = []

        # Check facts first
        if predicate in self.facts:
            self.execution_trace.append(f"  Found {len(self.facts[predicate])} facts for {predicate}")
            for fact_args in self.facts[predicate]:
                self.execution_trace.append(f"  Trying to unify with fact: {predicate}{fact_args}")
                bindings = self._try_unify(args, fact_args)
                if bindings is not None:
                    self.execution_trace.append(f"  ✓ Found fact: {predicate}{fact_args} with bindings {bindings}")
                    results.append({'bindings': bindings})
                else:
                    self.execution_trace.append(f"  ✗ Unification failed with fact: {predicate}{fact_args}")
        else:
            self.execution_trace.append(f"  No facts found for predicate: {predicate}")

        # Check rules
        self.execution_trace.append(f"  Checking {len(self.rules)} rules...")
        for i, (head, body) in enumerate(self.rules):
            head_pred, head_args = head
            self.execution_trace.append(f"  Rule {i + 1}: {head_pred}{head_args}")
            if head_pred == predicate:
                self.execution_trace.append(f"  Rule {i + 1} matches predicate {predicate}")
                bindings = self._try_unify(args, head_args)
                if bindings is not None:
                    self.execution_trace.append(f"  Rule {i + 1}: head unification successful with bindings {bindings}")
                    if self._evaluate_body_with_bindings(body, bindings):
                        self.execution_trace.append(f"  ✓ Rule {i + 1} satisfied")
                        results.append({'bindings': bindings})
                    else:
                        self.execution_trace.append(f"  ✗ Rule {i + 1} failed")
                else:
                    self.execution_trace.append(f"  ✗ Rule {i + 1}: head unification failed")
            else:
                self.execution_trace.append(f"  Rule {i + 1}: predicate mismatch ({head_pred} != {predicate})")

        self.execution_trace.append(f"Query result: {len(results)} results found")
        return results

    def _try_unify(self, pattern, fact):
        """Try to unify pattern with fact, return bindings if successful, None otherwise"""
        self.execution_trace.append(f"      Trying to unify pattern {pattern} with fact {fact}")

        if len(pattern) != len(fact):
            self.execution_trace.append(f"      Unification failed: length mismatch ({len(pattern)} != {len(fact)})")
            return None

        bindings = {}
        for i, (p, f) in enumerate(zip(pattern, fact)):
            self.execution_trace.append(f"      Position {i}: pattern '{p}' vs fact '{f}'")
            # FIXED: Check if the FACT contains a variable (not the pattern)
            if isinstance(f, str) and f.startswith('_'):
                # Variable in fact - bind it to the pattern value
                if f in bindings:
                    if bindings[f] != p:
                        self.execution_trace.append(f"      Unification failed: inconsistent binding for {f}")
                        return None  # Inconsistent binding
                else:
                    bindings[f] = p
                    self.execution_trace.append(f"      Bound variable {f} to {p}")
            elif isinstance(p, str) and p.startswith('_'):
                # Variable in pattern - bind it to the fact value
                if p in bindings:
                    if bindings[p] != f:
                        self.execution_trace.append(f"      Unification failed: inconsistent binding for {p}")
                        return None  # Inconsistent binding
                else:
                    bindings[p] = f
                    self.execution_trace.append(f"      Bound variable {p} to {f}")
            elif p != f:
                self.execution_trace.append(f"      Unification failed: {p} != {f}")
                return None  # Mismatch

        self.execution_trace.append(f"      Unification successful: {bindings}")
        return bindings

    def _evaluate_body_with_bindings(self, body: List[Tuple[str, tuple]], bindings: Dict) -> bool:
        """Evaluate rule body with variable bindings"""
        self.execution_trace.append(f"    Evaluating rule body with bindings: {bindings}")

        for i, (pred, args) in enumerate(body):
            self.execution_trace.append(f"    Step {i + 1}: {pred}({', '.join(map(str, args))})")

            # Substitute variables with their bindings
            substituted_args = []
            for arg in args:
                if isinstance(arg, str) and arg.startswith('_') and arg in bindings:
                    substituted_args.append(bindings[arg])
                else:
                    substituted_args.append(arg)

            self.execution_trace.append(f"    After substitution: {pred}({', '.join(map(str, substituted_args))})")

            # Handle special predicates
            if pred == "age_less_than":
                person, age_limit = substituted_args
                actual_age = self._calculate_age(person)
                result = actual_age < age_limit
                self.execution_trace.append(
                    f"    age_less_than({person}, {age_limit}) → age={actual_age}, result={result}")
                if not result:
                    return False
            elif pred == "income_less_than":
                person, income_limit = substituted_args
                self.execution_trace.append(
                    f"    Checking yearly_income facts: {self.facts.get('yearly_income', 'None')}")
                if 'yearly_income' in self.facts:
                    income_found = False
                    for fact_args in self.facts['yearly_income']:
                        self.execution_trace.append(f"      Checking fact: {fact_args}")
                        if fact_args[0] == person:
                            actual_income = fact_args[1]
                            result = actual_income < income_limit
                            self.execution_trace.append(
                                f"    income_less_than({person}, {income_limit}) → income={actual_income}, result={result}")
                            if not result:
                                return False
                            income_found = True
                            break
                    if not income_found:
                        self.execution_trace.append(
                            f"    income_less_than({person}, {income_limit}) → no income found for person, result=False")
                        return False
                else:
                    self.execution_trace.append(
                        f"    income_less_than({person}, {income_limit}) → no yearly_income facts found, result=False")
                    return False
            elif pred == "has_child_under_18":
                person = substituted_args[0]
                self.execution_trace.append(f"    Checking has_child_under_18({person})")
                self.execution_trace.append(f"    has_child facts: {self.facts.get('has_child', 'None')}")
                self.execution_trace.append(f"    birthdate facts: {self.facts.get('birthdate', 'None')}")

                if 'has_child' in self.facts:
                    has_child_under_18 = False
                    for parent, child in self.facts['has_child']:
                        if parent == person:
                            self.execution_trace.append(f"      Found child {child} for parent {parent}")
                            child_age = self._calculate_age(child)
                            self.execution_trace.append(f"      Child {child} age: {child_age}")
                            if child_age < 18:
                                self.execution_trace.append(
                                    f"    has_child_under_18({person}) → found child {child} age {child_age} < 18, result=True")
                                has_child_under_18 = True
                                break
                    if not has_child_under_18:
                        self.execution_trace.append(
                            f"    has_child_under_18({person}) → no children under 18 found, result=False")
                        return False
                else:
                    self.execution_trace.append(f"    has_child_under_18({person}) → no children found, result=False")
                    return False
            else:
                # Regular predicate - query it
                self.execution_trace.append(
                    f"    Querying regular predicate: {pred}({', '.join(map(str, substituted_args))})")
                sub_results = self.query(pred, *substituted_args)
                if not sub_results:
                    self.execution_trace.append(
                        f"    {pred}({', '.join(map(str, substituted_args))}) → no results found, FAILED")
                    return False
                else:
                    self.execution_trace.append(
                        f"    {pred}({', '.join(map(str, substituted_args))}) → found {len(sub_results)} results, PASSED")

        self.execution_trace.append("    ✓ All rule body conditions satisfied!")
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


class SemanticBrowserWeb:
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
then the kindergeld_amount is 500 euros per month.

If a person is eligible for Kindergeld 
and the person has 3 or more children
then the kindergeld_amount is 750 plus 250 times (number_of_children minus 3) euros per month.""",

            "tax_benefits": """If a person's yearly_income is below 30000 euros
and the person has tax_residence in Germany
then the person is eligible for low_income_tax_relief.

If a person is eligible for low_income_tax_relief
and the person has children
then the person gets additional_family_tax_benefits.""",

            "student_support": """If a person is a student
and the person is younger than 25 years
and the person's parents yearly_income is below 50000 euros
then the person is eligible for student_support.

If a person is eligible for student_support
and the person studies full_time
then the student_support_amount is 400 euros per month."""
        }

        self.example_queries = [
            "Is maria_schmidt eligible for Kindergeld?",
            "Who is eligible for low_income_tax_relief?",
            "What is the kindergeld_amount for maria_schmidt?",
            "Who has children?",
            "Who lives in Germany?"
        ]

    def _setup_test_db(self):
        """Setup test database with more diverse data"""
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

        # Insert diverse test data
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
            (67893, 12347, 2008, 5, 10),  # Anna's children (one over 18)
            (67894, 12347, 2020, 9, 3),
        ]

        cursor.executemany("""
            INSERT INTO children (id, parent_id, birth_year, birth_month, birth_day)
            VALUES (?, ?, ?, ?, ?)
        """, test_children)

        conn.commit()
        conn.close()

    def sql_to_ace(self) -> List[str]:
        """Convert all database data to ACE facts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all persons
        cursor.execute("SELECT * FROM persons")
        persons = cursor.fetchall()

        # Get all children
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

            # Find parent name
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM persons WHERE id = ?", (parent_id,))
            parent_name = cursor.fetchone()[0].replace(' ', '_').lower()
            conn.close()

            ace_facts.append(f"{child_ace} is a child.")
            ace_facts.append(f"{parent_name} has child {child_ace}.")
            ace_facts.append(f"{child_ace} has a birthdate of {birth_year}-{birth_month:02d}-{birth_day:02d}.")

        return ace_facts

    def parse_ace_rules(self, ace_rules: str):
        """Parse ACE rules and add to Prolog (simplified parser)"""
        self.prolog.clear()

        # Add facts from database
        ace_facts = self.sql_to_ace()
        self.prolog.execution_trace.append(f"Loading {len(ace_facts)} facts from database:")
        for fact in ace_facts:
            self.prolog.execution_trace.append(f"  {fact}")
            self._parse_ace_fact(fact)

        # Show what facts were actually parsed
        self.prolog.execution_trace.append("\nParsed facts summary:")
        for predicate, facts in self.prolog.facts.items():
            self.prolog.execution_trace.append(f"  {predicate}: {facts}")

        # Parse and add rules (simplified - in reality would need full ACE parser)
        # FIXED: Always add kindergeld rules when parsing any rules
        if "kindergeld" in ace_rules.lower() or "If a person has children" in ace_rules:
            self._add_kindergeld_rules()
        if "tax_relief" in ace_rules.lower() or "low_income_tax_relief" in ace_rules.lower():
            self._add_tax_relief_rules()
        if "student_support" in ace_rules.lower():
            self._add_student_support_rules()

        # Show what rules were added
        self.prolog.execution_trace.append(f"\nAdded {len(self.prolog.rules)} rules:")
        for i, (head, body) in enumerate(self.prolog.rules):
            head_str = f"{head[0]}({', '.join(map(str, head[1]))})"
            body_str = " AND ".join([f"{b[0]}({', '.join(map(str, b[1]))})" for b in body])
            self.prolog.execution_trace.append(f"  Rule {i + 1}: {head_str} :- {body_str}")

    def parse_ace_rules_with_custom_facts(self, ace_rules: str, custom_facts: str = ""):
        """Parse ACE rules and add to Prolog with custom facts override"""
        self.prolog.clear()

        # If custom facts are provided, use those instead of database
        if custom_facts.strip():
            self.prolog.execution_trace.append("Loading custom facts:")
            fact_lines = [line.strip() for line in custom_facts.split('\n') if line.strip()]
            for fact in fact_lines:
                self.prolog.execution_trace.append(f"  {fact}")
                self._parse_ace_fact(fact)
        else:
            # Add facts from database
            ace_facts = self.sql_to_ace()
            self.prolog.execution_trace.append(f"Loading {len(ace_facts)} facts from database:")
            for fact in ace_facts:
                self.prolog.execution_trace.append(f"  {fact}")
                self._parse_ace_fact(fact)

        # Show what facts were actually parsed
        self.prolog.execution_trace.append("\nParsed facts summary:")
        for predicate, facts in self.prolog.facts.items():
            self.prolog.execution_trace.append(f"  {predicate}: {facts}")

        # Parse and add rules
        if "kindergeld" in ace_rules.lower() or "If a person has children" in ace_rules:
            self._add_kindergeld_rules()
        if "tax_relief" in ace_rules.lower() or "low_income_tax_relief" in ace_rules.lower():
            self._add_tax_relief_rules()
        if "student_support" in ace_rules.lower():
            self._add_student_support_rules()

        # Show what rules were added
        self.prolog.execution_trace.append(f"\nAdded {len(self.prolog.rules)} rules:")
        for i, (head, body) in enumerate(self.prolog.rules):
            head_str = f"{head[0]}({', '.join(map(str, head[1]))})"
            body_str = " AND ".join([f"{b[0]}({', '.join(map(str, b[1]))})" for b in body])
            self.prolog.execution_trace.append(f"  Rule {i + 1}: {head_str} :- {body_str}")

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
        elif " has age " in ace_fact:
            match = re.search(r"(\w+) has age (\d+) years", ace_fact)
            if match:
                self.prolog.add_fact("age", match.group(1), int(match.group(2)))
        elif " studies full_time" in ace_fact:
            match = re.search(r"(\w+) studies full_time", ace_fact)
            if match:
                self.prolog.add_fact("studies_full_time", match.group(1))

    def _add_kindergeld_rules(self):
        """Add Kindergeld rules - FIXED VERSION"""
        # Main eligibility rule - FIXED: Remove extra parentheses around _person
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

        self.prolog.add_rule(
            ("gets_additional_family_tax_benefits", ("_person",)),
            [
                ("eligible_for_low_income_tax_relief", ("_person",)),
                ("has_child", ("_person", "_child"))
            ]
        )

    def _add_student_support_rules(self):
        """Add student support rules"""
        self.prolog.add_rule(
            ("eligible_for_student_support", ("_person",)),
            [
                ("student", ("_person",)),
                ("age_less_than", ("_person", 25)),
                # Simplified: would need parent income lookup
            ]
        )


# Flask app
app = Flask(__name__)
browser = SemanticBrowserWeb()


@app.route('/')
def index():
    # Get current facts from database
    current_facts = "\n".join(browser.sql_to_ace())

    return render_template('index.html',
                           default_rules=browser.default_rules,
                           example_queries=browser.example_queries,
                           current_facts=current_facts)


@app.route('/execute', methods=['POST'])
def execute_query():
    data = request.get_json()
    ace_rules = data.get('rules', '')
    query = data.get('query', '')
    custom_facts = data.get('facts', '')

    try:
        # Parse rules and setup knowledge base (with optional custom facts)
        browser.parse_ace_rules_with_custom_facts(ace_rules, custom_facts)

        # Parse query (simplified but more robust)
        query_lower = query.lower().strip('?').strip()
        query_parts = query_lower.split()

        results = []
        answer = ""

        if query_lower.startswith("is ") and len(query_parts) >= 2:
            # "Is maria_schmidt eligible for Kindergeld?"
            person = query_parts[1]

            if "eligible" in query_lower:
                if "kindergeld" in query_lower:
                    query_results = browser.prolog.query("eligible_for_kindergeld", person)
                    browser.prolog.execution_trace.append(
                        f"DEBUG: Query called with predicate='eligible_for_kindergeld', person='{person}'")
                    browser.prolog.execution_trace.append(f"DEBUG: Query results: {query_results}")
                    if query_results:
                        answer = f"Yes, {person} is eligible for Kindergeld."
                        results = [{"result": "eligible", "person": person, "benefit": "Kindergeld"}]
                    else:
                        answer = f"No, {person} is not eligible for Kindergeld."
                        results = [{"result": "not eligible", "person": person, "benefit": "Kindergeld"}]
                elif "tax_relief" in query_lower or "low_income_tax_relief" in query_lower:
                    query_results = browser.prolog.query("eligible_for_low_income_tax_relief", person)
                    if query_results:
                        answer = f"Yes, {person} is eligible for low income tax relief."
                        results = [{"result": "eligible", "person": person, "benefit": "low_income_tax_relief"}]
                    else:
                        answer = f"No, {person} is not eligible for low income tax relief."
                        results = [{"result": "not eligible", "person": person, "benefit": "low_income_tax_relief"}]
                elif "student_support" in query_lower:
                    query_results = browser.prolog.query("eligible_for_student_support", person)
                    if query_results:
                        answer = f"Yes, {person} is eligible for student support."
                        results = [{"result": "eligible", "person": person, "benefit": "student_support"}]
                    else:
                        answer = f"No, {person} is not eligible for student support."
                        results = [{"result": "not eligible", "person": person, "benefit": "student_support"}]

        elif query_lower.startswith("who "):
            # "Who is eligible for ..." or "Who has children?"
            if "eligible" in query_lower:
                if "kindergeld" in query_lower:
                    # Find all persons and check eligibility
                    persons = browser.prolog.facts.get("person", [])
                    eligible_persons = []
                    for (person,) in persons:
                        if browser.prolog.query("eligible_for_kindergeld", person):
                            eligible_persons.append(person)

                    if eligible_persons:
                        answer = f"The following people are eligible for Kindergeld: {', '.join(eligible_persons)}"
                        results = [{"person": person, "benefit": "Kindergeld", "result": "eligible"} for person in
                                   eligible_persons]
                    else:
                        answer = "No one is eligible for Kindergeld."

                elif "tax_relief" in query_lower or "low_income_tax_relief" in query_lower:
                    persons = browser.prolog.facts.get("person", [])
                    eligible_persons = []
                    for (person,) in persons:
                        if browser.prolog.query("eligible_for_low_income_tax_relief", person):
                            eligible_persons.append(person)

                    if eligible_persons:
                        answer = f"The following people are eligible for low income tax relief: {', '.join(eligible_persons)}"
                        results = [{"person": person, "benefit": "low_income_tax_relief", "result": "eligible"} for
                                   person in eligible_persons]
                    else:
                        answer = "No one is eligible for low income tax relief."

            elif "children" in query_lower or "child" in query_lower:
                # "Who has children?"
                if "has_child" in browser.prolog.facts:
                    parents = list(set([parent for parent, child in browser.prolog.facts["has_child"]]))
                    if parents:
                        answer = f"The following people have children: {', '.join(parents)}"
                        results = [{"person": parent, "has": "children"} for parent in parents]
                    else:
                        answer = "No one has children."

        elif query_lower.startswith("what "):
            # "What is the kindergeld_amount for maria_schmidt?"
            if "kindergeld_amount" in query_lower:
                # Extract person name (simplified)
                for word in query_parts:
                    if word not in ["what", "is", "the", "kindergeld_amount", "for", "?"]:
                        person = word
                        # Check if eligible first
                        if browser.prolog.query("eligible_for_kindergeld", person):
                            # Count children to determine amount
                            if "has_child" in browser.prolog.facts:
                                children_count = len([f for f in browser.prolog.facts["has_child"] if f[0] == person])
                                if children_count == 1:
                                    amount = 250
                                elif children_count == 2:
                                    amount = 500
                                else:  # 3 or more
                                    amount = 750 + 250 * (children_count - 3)

                                answer = f"The Kindergeld amount for {person} is {amount} euros per month (for {children_count} children)."
                                results = [
                                    {"person": person, "kindergeld_amount": amount, "children_count": children_count}]
                            else:
                                answer = f"{person} has no children recorded."
                        else:
                            answer = f"{person} is not eligible for Kindergeld."
                        break

        # If no specific parsing worked, try a generic approach
        if not results and not answer:
            answer = "I couldn't parse that query. Please try one of the example queries."

        return jsonify({
            'success': True,
            'results': results,
            'answer': answer,
            'execution_trace': browser.prolog.execution_trace,
            'facts_count': sum(len(facts) for facts in browser.prolog.facts.values()),
            'rules_count': len(browser.prolog.rules)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'execution_trace': browser.prolog.execution_trace if hasattr(browser, 'prolog') else []
        })


@app.route('/database')
def view_database():
    """View current database content"""
    conn = sqlite3.connect(browser.db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM persons")
    persons = cursor.fetchall()

    cursor.execute("SELECT c.*, p.name as parent_name FROM children c JOIN persons p ON c.parent_id = p.id")
    children = cursor.fetchall()

    conn.close()

    return jsonify({
        'persons': persons,
        'children': children
    })


if __name__ == '__main__':
    # Create templates directory and HTML template
    os.makedirs('templates', exist_ok=True)

    html_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Semantic Web Browser - Enhanced</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { background: #4CAF50; color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .section { background: white; padding: 20px; margin-bottom: 20px; border-radius: 5px; border: 1px solid #ddd; }
        .two-column { display: flex; gap: 20px; }
        .column { flex: 1; }
        textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 3px; font-family: monospace; }
        button { background: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 3px; cursor: pointer; margin: 5px; }
        button:hover { background: #45a049; }
        .secondary-button { background: #2196F3; }
        .secondary-button:hover { background: #0b7dda; }
        .results { background: #f9f9f9; padding: 15px; border-radius: 3px; margin-top: 10px; }
        .success { color: green; font-weight: bold; }
        .error { color: red; font-weight: bold; }
        pre { background: #f0f0f0; padding: 10px; border-radius: 3px; overflow-x: auto; }
        .example { background: #e7f3ff; padding: 5px 10px; margin: 2px; border-radius: 3px; cursor: pointer; display: inline-block; }
        .example:hover { background: #d0e7ff; }
        .answer-box { background: #e8f5e8; border: 2px solid #4CAF50; padding: 15px; border-radius: 5px; margin: 10px 0; }
        .answer-box h4 { margin-top: 0; color: #2e7d32; }
        .fact-editor { background: #fff3e0; border: 2px solid #ff9800; }
        .fact-examples { background: #f3e5f5; padding: 10px; border-radius: 3px; margin: 10px 0; }
        h4 { margin-top: 0; color: #333; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Semantic Web Browser - Enhanced</h1>
            <p>ACE Rules → Custom Facts → Prolog → Results Pipeline</p>
        </div>

        <div class="two-column">
            <div class="column">
                <div class="section">
                    <h3>1. ACE Rules</h3>
                    <button onclick="loadKindergeld()">Load Kindergeld Rules</button>
                    <button onclick="loadTaxRelief()">Load Tax Relief Rules</button>
                    <button onclick="clearRules()">Clear Rules</button>
                    <br><br>
                    <textarea id="aceRules" rows="12" placeholder="Enter your ACE rules here..."></textarea>
                </div>
            </div>

            <div class="column">
                <div class="section fact-editor">
                    <h3>2. Edit Facts About Persons</h3>
                    <div style="display: flex; gap: 10px; margin-bottom: 10px;">
                        <button class="secondary-button" onclick="loadDatabaseFacts()">Load from Database</button>
                        <button class="secondary-button" onclick="addExamplePerson()">Add Example Person</button>
                        <button onclick="clearFacts()">Clear Facts</button>
                    </div>
                    <textarea id="factsEditor" rows="12" placeholder="Enter facts in ACE format, e.g.:
john_doe is a person.
john_doe has a yearly_income of 35000 euros.
john_doe has tax_residence in Germany.
john_doe has child child_123.
child_123 has a birthdate of 2010-05-15."></textarea>

                    <div class="fact-examples">
                        <strong>📝 Fact Examples:</strong><br>
                        <small>
                        • <code>person_name is a person.</code><br>
                        • <code>person_name has a yearly_income of 45000 euros.</code><br>
                        • <code>person_name has tax_residence in Germany.</code><br>
                        • <code>person_name has child child_name.</code><br>
                        • <code>child_name has a birthdate of 2015-03-20.</code><br>
                        • <code>person_name is a student.</code><br>
                        • <code>person_name studies full_time.</code>
                        </small>
                    </div>
                </div>
            </div>
        </div>

        <div class="section">
            <h3>3. Query</h3>
            <textarea id="query" rows="3" placeholder="Enter your query here...">Is maria_schmidt eligible for Kindergeld?</textarea>
            <br><br>
            <strong>Example queries:</strong><br>
            <span class="example" onclick="setQuery('Is maria_schmidt eligible for Kindergeld?')">Is maria_schmidt eligible for Kindergeld?</span>
            <span class="example" onclick="setQuery('Who is eligible for low_income_tax_relief?')">Who is eligible for tax relief?</span>
            <span class="example" onclick="setQuery('Who has children?')">Who has children?</span>
            <span class="example" onclick="setQuery('What is the kindergeld_amount for maria_schmidt?')">What is the kindergeld amount for maria_schmidt?</span>
            <br><br>
            <button onclick="executeQuery()">🚀 Execute Query</button>
            <button class="secondary-button" onclick="viewDatabase()">📊 View Database</button>
        </div>

        <div class="section">
            <h3>4. Results</h3>
            <div id="results" class="results" style="display: none;">
                <div id="resultContent"></div>
            </div>
            <div id="trace" style="display: none;">
                <h4>Execution Trace:</h4>
                <pre id="traceContent"></pre>
            </div>
        </div>
    </div>

    <script>
        // Store the current facts from the server
        const currentFactsFromDB = {{ current_facts|tojson }};

        // Embedded rule templates
        const kindergeldRules = `If a person has children 
and the person's yearly_income is below 68000 euros
and at least one child is younger than 18 years
and the person has tax_residence in Germany
then the person is eligible for Kindergeld.`;

        const taxReliefRules = `If a person's yearly_income is below 30000 euros
and the person has tax_residence in Germany
then the person is eligible for low_income_tax_relief.

If a person is eligible for low_income_tax_relief
and the person has children
then the person gets additional_family_tax_benefits.`;

        const examplePersonFacts = `john_doe is a person.
john_doe has a yearly_income of 35000 euros.
john_doe has tax_residence in Germany.
john_doe has child child_456.
child_456 has a birthdate of 2010-05-15.`;

        function loadKindergeld() {
            document.getElementById('aceRules').value = kindergeldRules;
        }

        function loadTaxRelief() {
            document.getElementById('aceRules').value = taxReliefRules;
        }

        function clearRules() {
            document.getElementById('aceRules').value = '';
        }

        function loadDatabaseFacts() {
            document.getElementById('factsEditor').value = currentFactsFromDB;
        }

        function addExamplePerson() {
            const currentFacts = document.getElementById('factsEditor').value;
            const separator = currentFacts.trim() ? '\\n\\n' : '';
            document.getElementById('factsEditor').value = currentFacts + separator + examplePersonFacts;
        }

        function clearFacts() {
            document.getElementById('factsEditor').value = '';
        }

        function setQuery(query) {
            document.getElementById('query').value = query;
        }

        async function executeQuery() {
            const rules = document.getElementById('aceRules').value;
            const query = document.getElementById('query').value;
            const facts = document.getElementById('factsEditor').value;

            const resultsDiv = document.getElementById('results');
            const traceDiv = document.getElementById('trace');
            const resultContent = document.getElementById('resultContent');
            const traceContent = document.getElementById('traceContent');

            try {
                const response = await fetch('/execute', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ rules, query, facts })
                });

                const data = await response.json();

                if (data.success) {
                    let html = `<div class="success">✓ Query executed successfully</div>`;

                    // Display the answer prominently
                    if (data.answer) {
                        html += `<div class="answer-box">
                            <h4>Answer:</h4>
                            <p>${data.answer}</p>
                        </div>`;
                    }

                    // Display structured results
                    if (data.results && data.results.length > 0) {
                        html += `<p><strong>Detailed Results:</strong></p>
                                <pre>${JSON.stringify(data.results, null, 2)}</pre>`;
                    }

                    html += `<p><strong>Knowledge Base:</strong> ${data.facts_count} facts | ${data.rules_count} rules</p>`;

                    resultContent.innerHTML = html;
                } else {
                    resultContent.innerHTML = `
                        <div class="error">✗ Query failed</div>
                        <p><strong>Error:</strong> ${data.error}</p>
                    `;
                }

                traceContent.textContent = data.execution_trace.join('\\n');
                resultsDiv.style.display = 'block';
                traceDiv.style.display = 'block';

            } catch (error) {
                resultContent.innerHTML = `<div class="error">✗ Network error: ${error.message}</div>`;
                resultsDiv.style.display = 'block';
            }
        }

        async function viewDatabase() {
            try {
                const response = await fetch('/database');
                const data = await response.json();

                const resultContent = document.getElementById('resultContent');
                resultContent.innerHTML = `
                    <div class="success">📊 Database Content:</div>
                    <h4>Persons:</h4>
                    <pre>${JSON.stringify(data.persons, null, 2)}</pre>
                    <h4>Children:</h4>
                    <pre>${JSON.stringify(data.children, null, 2)}</pre>
                `;

                document.getElementById('results').style.display = 'block';
            } catch (error) {
                console.error('Error fetching database:', error);
            }
        }

        // Load default content on page load
        window.onload = function() {
            loadKindergeld();
            loadDatabaseFacts();
        };
    </script>
</body>
</html>'''

    with open('templates/index.html', 'w') as f:
        f.write(html_template)

    print("🚀 Starting Enhanced Semantic Web Browser Interface...")
    print("📊 Database initialized with sample data")
    print("✨ NEW: Editable facts text area added!")
    print("🌐 Open your browser to: http://localhost:5000")
    print("💡 Try editing facts and running queries!")

    app.run(debug=True, port=5000)