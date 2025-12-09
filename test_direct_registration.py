#!/usr/bin/env python
"""Direct test of registration without HTTP requests."""

from app import create_app
from app.models import db, Employee, EmployeeRole, get_next_employee_id, Tenant
from datetime import datetime

# Create app
app = create_app()

with app.app_context():
    print("Testing direct database operations...")
    
    # Get tenant
    tenant = Tenant.query.first()
    if not tenant:
        print("✗ No tenant found")
        exit(1)
    
    tid = tenant.tenant_id
    print(f"✓ Using tenant_id: {tid}")
    
    # Test get_next_employee_id()
    print("\nTesting get_next_employee_id()...")
    next_id = get_next_employee_id(tid)
    print(f"  Next employee_id: {next_id}")
    
    # Try to create an employee
    print("\nCreating test employee...")
    try:
        emp = Employee(
            tenant_id=tid,
            employee_id=next_id,
            first_name="Test",
            last_name="User",
            email="testuser@example.com",
            role=EmployeeRole.seller,
            active=True
        )
        db.session.add(emp)
        db.session.flush()
        print(f"  ✓ Employee created with ID: {emp.id}, employee_id: {emp.employee_id}")
        
        db.session.commit()
        print("  ✓ Employee committed to database")
        
        # Verify by querying
        emp_check = Employee.query.filter_by(tenant_id=tid, email="testuser@example.com").first()
        if emp_check:
            print(f"  ✓ Employee found in database: {emp_check.first_name} {emp_check.last_name}")
        else:
            print("  ✗ Employee not found after commit")
            
    except Exception as e:
        db.session.rollback()
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()

print("\n✓ Test completed!")
