#!/usr/bin/env python
"""Comprehensive test of database operations and app initialization."""

from app import create_app
from app.models import (
    db, Employee, EmployeeRole, Tenant, Region, Location, Customer, Product,
    get_next_employee_id, get_next_region_id, get_next_location_id, get_next_customer_id, get_next_product_id
)
from datetime import datetime, date

print("=" * 60)
print("COMPREHENSIVE DATABASE TEST")
print("=" * 60)

app = create_app()

with app.app_context():
    print("\n✓ App created and context established")
    
    # Get tenant
    tenant = Tenant.query.first()
    if not tenant:
        print("✗ No tenant found")
        exit(1)
    
    tid = tenant.tenant_id
    print(f"✓ Using tenant_id: {tid} ({tenant.name})")
    
    # Test creating various resources with manual ID generation
    print("\n" + "-" * 60)
    print("Testing resource creation with manual ID generation:")
    print("-" * 60)
    
    try:
        # 1. Create a region
        print("\n1. Creating Region...")
        next_region_id = get_next_region_id(tid)
        region = Region(
            tenant_id=tid,
            region_id=next_region_id,
            name=f"Region-{date.today().isoformat()}"
        )
        db.session.add(region)
        db.session.flush()
        print(f"   ✓ Region created: tenant_id={region.tenant_id}, region_id={region.region_id}")
        
        # 2. Create a location
        print("\n2. Creating Location...")
        next_loc_id = get_next_location_id(tid)
        location = Location(
            tenant_id=tid,
            location_id=next_loc_id,
            name=f"Location-{date.today().isoformat()}",
            address="Test Address 123",
            region_id=region.region_id
        )
        db.session.add(location)
        db.session.flush()
        print(f"   ✓ Location created: tenant_id={location.tenant_id}, location_id={location.location_id}")
        
        # 3. Create a customer
        print("\n3. Creating Customer...")
        next_cust_id = get_next_customer_id(tid)
        customer = Customer(
            tenant_id=tid,
            customer_id=next_cust_id,
            name=f"Customer-{date.today().isoformat()}",
            municipality="Test City",
            region_id=region.region_id,
            email=f"customer-{date.today().isoformat()}@test.com"
        )
        db.session.add(customer)
        db.session.flush()
        print(f"   ✓ Customer created: tenant_id={customer.tenant_id}, customer_id={customer.customer_id}")
        
        # 4. Create a product
        print("\n4. Creating Product...")
        next_prod_id = get_next_product_id(tid)
        product = Product(
            tenant_id=tid,
            product_id=next_prod_id,
            name=f"Product-{date.today().isoformat()}",
            category="Test",
            stock_qty=100
        )
        db.session.add(product)
        db.session.flush()
        print(f"   ✓ Product created: tenant_id={product.tenant_id}, product_id={product.product_id}")
        
        # 5. Create an employee (seller)
        print("\n5. Creating Employee (Seller)...")
        next_emp_id = get_next_employee_id(tid)
        seller = Employee(
            tenant_id=tid,
            employee_id=next_emp_id,
            first_name="Test",
            last_name="Seller",
            email=f"seller-{date.today().isoformat()}@test.com",
            role=EmployeeRole.seller,
            active=True,
            location_id=location.location_id
        )
        db.session.add(seller)
        db.session.flush()
        print(f"   ✓ Seller created: tenant_id={seller.tenant_id}, employee_id={seller.employee_id}, ID={seller.id}")
        
        # 6. Create another employee (driver)
        print("\n6. Creating Employee (Driver)...")
        next_emp_id = get_next_employee_id(tid)
        driver = Employee(
            tenant_id=tid,
            employee_id=next_emp_id,
            first_name="Test",
            last_name="Driver",
            email=f"driver-{date.today().isoformat()}@test.com",
            role=EmployeeRole.driver,
            active=True,
            location_id=location.location_id
        )
        db.session.add(driver)
        db.session.flush()
        print(f"   ✓ Driver created: tenant_id={driver.tenant_id}, employee_id={driver.employee_id}, ID={driver.id}")
        
        # Commit all changes
        db.session.commit()
        print("\n✓ All changes committed to database")
        
        # Verify by querying
        print("\n" + "-" * 60)
        print("Verifying created resources:")
        print("-" * 60)
        
        region_check = Region.query.filter_by(tenant_id=tid, region_id=region.region_id).first()
        print(f"\n1. Region: {'✓ Found' if region_check else '✗ Not found'}")
        
        location_check = Location.query.filter_by(tenant_id=tid, location_id=location.location_id).first()
        print(f"2. Location: {'✓ Found' if location_check else '✗ Not found'}")
        
        customer_check = Customer.query.filter_by(tenant_id=tid, customer_id=customer.customer_id).first()
        print(f"3. Customer: {'✓ Found' if customer_check else '✗ Not found'}")
        
        product_check = Product.query.filter_by(tenant_id=tid, product_id=product.product_id).first()
        print(f"4. Product: {'✓ Found' if product_check else '✗ Not found'}")
        
        seller_check = Employee.query.filter_by(tenant_id=tid, employee_id=seller.employee_id).first()
        print(f"5. Seller: {'✓ Found' if seller_check else '✗ Not found'}")
        
        driver_check = Employee.query.filter_by(tenant_id=tid, employee_id=driver.employee_id).first()
        print(f"6. Driver: {'✓ Found' if driver_check else '✗ Not found'}")
        
        emp_count = Employee.query.filter_by(tenant_id=tid).count()
        print(f"\nTotal employees for tenant {tid}: {emp_count}")
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        
    except Exception as e:
        db.session.rollback()
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
