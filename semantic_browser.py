#!/usr/bin/env python3
"""
Semantic Browser MVP - SQL → ACE → Prolog → Execution Pipeline
Demonstrates the core concept with Kindergeld eligibility example
"""

import sqlite3
import re
from datetime import datetime, date
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
import json

# Simple Prolog-like inference engine
class PrologEngine:
    def __init__(self):
        self.facts = {}  # predicate_name -> list of tuples
        self.rules = []  # list of (head, body) tuples
        
    def add_fact(self, predicate: str, *args):
        """Add a fact to the knowledge base"""
        if predicate not in self.facts:
            self.facts[predicate] = []
        self.facts[predicate].append(args)
        print(f"  Added fact: {predicate}({', '.join(map(str, args))})")
    
    def add_rule(self, head: Tuple[str, tuple], body: List[Tuple[str, tuple]]):
        """Add a rule to the knowledge base"""
        self.rules.append((head, body))
        head_str = f"{head[0]}({', '.join(map(str, head[1]))})"
        body_str = " AND ".join([f"{b[0]}({', '.join(map(str, b[1]))})" for b in body])
        print(f"  Added rule: {head_str} :- {body_str}")
    
    def query(self, predicate: str, *args) -> List[Dict]:
        """Query the knowledge base"""
        print(f"\n--- Prolog Query: {predicate}({', '.join(map(str, args))}) ---")
        results = []
        
        # Check facts first
        if predicate in self.facts:
            for fact_args in self.facts[predicate]:
                if self._unify(args, fact_args):
                    print(f"  ✓ Found fact: {predicate}{fact_args}")
                    results.append({'bindings': dict(zip(args, fact_args))})
        
        # Check rules
        for head, body in self.rules:
            head_pred, head_args = head
            if head_pred == predicate and self._unify(args, head_args):
                print(f"  Checking rule: {head_pred}{head_args}")
                if self._evaluate_body(body):
                    print(f"  ✓ Rule satisfied")
                    results.append({'bindings': dict(zip(args, head_args))})
                else:
                    print(f"  ✗ Rule failed")
        
        return results
    
    def _unify(self, pattern, fact):
        """Simple unification (just checks if compatible)"""
        if len(pattern) != len(fact):
            return False
        for p, f in zip(pattern, fact):
            if isinstance(p, str) and p.startswith('_'):
                continue  # Variable, matches anything
            if p != f:
                return False
        return True
    
    def _evaluate_body(self, body: List[Tuple[str, tuple]]) -> bool:
        """Evaluate rule body (all conditions must be true)"""
        for pred, args in body:
            if pred == "age_less_than":
                # Special built-in predicate
                person, age_limit = args
                actual_age = self._calculate_age(person)
                result = actual_age < age_limit
                print(f"    age_less_than({person}, {age_limit}) → age={actual_age}, result={result}")
                if not result:
                    return False
            elif pred == "income_less_than":
                # Special built-in predicate  
                person, income_limit = args
                if 'yearly_income' in self.facts:
                    for fact_args in self.facts['yearly_income']:
                        if fact_args[0] == person:
                            actual_income = fact_args[1]
                            result = actual_income < income_limit
                            print(f"    income_less_than({person}, {income_limit}) → income={actual_income}, result={result}")
                            if not result:
                                return False
                            break
                    else:
                        return False
            else:
                # Regular predicate
                results = self.query(pred, *args)
                if not results:
                    return False
        return True
    
    def _calculate_age(self, person: str) -> int:
        """Calculate age from birthdate facts"""
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

@dataclass
class SchemaMapping:
    source_field: str
    target_concept: str
    precision: float

class SemanticBrowser:
    def __init__(self, db_path: str = "family_data.db"):
        self.db_path = db_path
        self.prolog = PrologEngine()
        self.schema_mappings = {}
        self.precision_controller = 0.5
        
        # Initialize test database
        self._setup_test_db()
    
    def _setup_test_db(self):
        """Create test database with family data"""
        print(f"Setting up database at: {self.db_path}")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Drop existing tables to ensure clean state
        cursor.execute("DROP TABLE IF EXISTS children")
        cursor.execute("DROP TABLE IF EXISTS persons")
        
        # Create tables
        cursor.execute("""
            CREATE TABLE persons (
                id INTEGER PRIMARY KEY,
                name TEXT,
                annual_gross_income INTEGER,
                tax_residence_country TEXT
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
        cursor.execute("""
            INSERT INTO persons (id, name, annual_gross_income, tax_residence_country)
            VALUES (12345, 'Maria Schmidt', 45000, 'Germany')
        """)
        
        cursor.execute("""
            INSERT INTO children (id, parent_id, birth_year, birth_month, birth_day)
            VALUES (67890, 12345, 2010, 3, 15)
        """)
        
        cursor.execute("""
            INSERT INTO children (id, parent_id, birth_year, birth_month, birth_day) 
            VALUES (67891, 12345, 2018, 7, 22)
        """)
        
        conn.commit()
        conn.close()
        
        # Verify data was inserted
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM persons")
        person_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM children") 
        children_count = cursor.fetchone()[0]
        conn.close()
        
        print(f"✓ Test database initialized: {person_count} persons, {children_count} children")
    
    def add_schema_mapping(self, source_field: str, target_concept: str, precision: float):
        """Add schema mapping for SQL → ACE conversion"""
        self.schema_mappings[source_field] = SchemaMapping(source_field, target_concept, precision)
    
    def sql_to_ace(self, query: str, person_name: str) -> List[str]:
        """Convert SQL results to ACE facts"""
        print(f"\n--- Phase 2: SQL Query Execution ---")
        print(f"Query: {query}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get person data
        cursor.execute("SELECT * FROM persons WHERE name = ?", (person_name,))
        person_row = cursor.fetchone()
        
        # Get children data  
        cursor.execute("SELECT * FROM children WHERE parent_id = ?", (person_row[0],))
        children_rows = cursor.fetchall()
        
        conn.close()
        
        print(f"Person data: {person_row}")
        print(f"Children data: {children_rows}")
        
        print(f"\n--- Phase 3: SQL → ACE Conversion ---")
        
        ace_facts = []
        person_ace_name = person_name.replace(' ', '_').lower()
        
        # Convert person data to ACE
        ace_facts.append(f"{person_ace_name} is a person.")
        
        if person_row[2]:  # annual_gross_income
            ace_facts.append(f"{person_ace_name} has a yearly_income of {person_row[2]} euros.")
            
        if person_row[3]:  # tax_residence_country
            ace_facts.append(f"{person_ace_name} has tax_residence in {person_row[3]}.")
        
        # Convert children data to ACE
        for i, child_row in enumerate(children_rows):
            child_ace_name = f"child_{child_row[0]}"
            ace_facts.append(f"{child_ace_name} is a child.")
            ace_facts.append(f"{person_ace_name} has child {child_ace_name}.")
            ace_facts.append(f"{child_ace_name} has a birthdate of {child_row[2]}-{child_row[3]:02d}-{child_row[4]:02d}.")
        
        for fact in ace_facts:
            print(f"  {fact}")
        
        return ace_facts
    
    def ace_to_prolog(self, ace_facts: List[str], ace_rules: List[str]) -> None:
        """Convert ACE facts and rules to Prolog knowledge base"""
        print(f"\n--- Phase 4: ACE → Prolog Conversion ---")
        
        # Convert ACE facts to Prolog facts
        for fact in ace_facts:
            self._parse_ace_fact(fact)
        
        # Add hardcoded Kindergeld rules (in real implementation, these would be parsed from ACE)
        self._add_kindergeld_rules()
    
    def _parse_ace_fact(self, ace_fact: str):
        """Parse an ACE fact and add to Prolog knowledge base"""
        ace_fact = ace_fact.strip('.')
        
        # Parse different ACE patterns
        if " is a " in ace_fact:
            # "maria_schmidt is a person" → person(maria_schmidt)
            parts = ace_fact.split(" is a ")
            self.prolog.add_fact(parts[1], parts[0])
            
        elif " has a yearly_income of " in ace_fact:
            # "maria_schmidt has a yearly_income of 45000 euros" → yearly_income(maria_schmidt, 45000)
            match = re.search(r"(\w+) has a yearly_income of (\d+) euros", ace_fact)
            if match:
                self.prolog.add_fact("yearly_income", match.group(1), int(match.group(2)))
                
        elif " has tax_residence in " in ace_fact:
            # "maria_schmidt has tax_residence in Germany" → tax_residence(maria_schmidt, germany)
            match = re.search(r"(\w+) has tax_residence in (\w+)", ace_fact)
            if match:
                self.prolog.add_fact("tax_residence", match.group(1), match.group(2).lower())
                
        elif " has child " in ace_fact:
            # "maria_schmidt has child child_67890" → has_child(maria_schmidt, child_67890)
            match = re.search(r"(\w+) has child (\w+)", ace_fact)
            if match:
                self.prolog.add_fact("has_child", match.group(1), match.group(2))
                
        elif " has a birthdate of " in ace_fact:
            # "child_67890 has a birthdate of 2010-03-15" → birthdate(child_67890, 2010, 3, 15)
            match = re.search(r"(\w+) has a birthdate of (\d{4})-(\d{2})-(\d{2})", ace_fact)
            if match:
                self.prolog.add_fact("birthdate", match.group(1), 
                                   int(match.group(2)), int(match.group(3)), int(match.group(4)))
    
    def _add_kindergeld_rules(self):
        """Add Kindergeld eligibility rules to Prolog knowledge base"""
        # Rule: eligible_for_kindergeld(Person) :- 
        #   person(Person), has_child(Person, _), income_less_than(Person, 68000), 
        #   has_child_under_18(Person), tax_residence(Person, germany)
        
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
        
        # Rule: has_child_under_18(Person) :- has_child(Person, Child), age_less_than(Child, 18)
        self.prolog.add_rule(
            ("has_child_under_18", ("_person",)),
            [
                ("has_child", ("_person", "_child")),
                ("age_less_than", ("_child", 18))
            ]
        )
    
    def execute_query(self, person_name: str) -> Dict[str, Any]:
        """Execute complete pipeline: SQL → ACE → Prolog → Results"""
        print("="*60)
        print("SEMANTIC BROWSER MVP - KINDERGELD ELIGIBILITY CHECK")
        print("="*60)
        
        person_ace_name = person_name.replace(' ', '_').lower()
        
        # Phase 1: SQL → ACE
        ace_facts = self.sql_to_ace("SELECT * FROM persons, children", person_name)
        
        # Phase 2: ACE → Prolog  
        self.ace_to_prolog(ace_facts, [])
        
        # Phase 3: Execute Prolog queries
        print(f"\n--- Phase 5: Prolog Query Execution ---")
        
        # Check eligibility
        eligibility_results = self.prolog.query("eligible_for_kindergeld", person_ace_name)
        is_eligible = len(eligibility_results) > 0
        
        # Calculate amount if eligible
        amount = 0
        if is_eligible:
            # Count children
            child_results = self.prolog.query("has_child", person_ace_name, "_child")
            num_children = len([r for r in self.prolog.facts.get("has_child", []) if r[0] == person_ace_name])
            
            if num_children == 1:
                amount = 250
            elif num_children == 2:
                amount = 500
            elif num_children >= 3:
                amount = 750 + (num_children - 3) * 250
        
        # Generate results
        result = {
            "person": person_name,
            "person_ace": person_ace_name,
            "eligible": is_eligible,
            "monthly_amount": amount,
            "annual_amount": amount * 12,
            "reasoning": {
                "eligibility_check": eligibility_results,
                "children_count": len([r for r in self.prolog.facts.get("has_child", []) if r[0] == person_ace_name])
            },
            "data_sources": {
                "local_db": {"precision": 0.2, "confidence": 1.0}
            }
        }
        
        return result

def main():
    """Run the MVP demonstration"""
    # Initialize semantic browser
    browser = SemanticBrowser()
    
    # Add schema mappings
    browser.add_schema_mapping("annual_gross_income", "yearly_income", 0.2)
    browser.add_schema_mapping("tax_residence_country", "tax_residence", 0.1)
    
    # Execute query
    result = browser.execute_query("Maria Schmidt")
    
    # Display results
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    print(json.dumps(result, indent=2))
    
    # Natural language summary
    print(f"\n--- Summary ---")
    if result["eligible"]:
        print(f"✓ {result['person']} is eligible for Kindergeld")
        print(f"✓ Monthly amount: €{result['monthly_amount']}")
        print(f"✓ Annual amount: €{result['annual_amount']}")
        print(f"✓ Based on {result['reasoning']['children_count']} children")
    else:
        print(f"✗ {result['person']} is not eligible for Kindergeld")

if __name__ == "__main__":
    main()
