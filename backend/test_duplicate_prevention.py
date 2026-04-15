#!/usr/bin/env python3
"""
Test script to verify duplicate interview prevention
Simulates form responses to test that:
1. First submission creates candidate and schedules interview
2. Duplicate submission (same email) is skipped
3. Database correctly tracks processed candidates
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from database import SessionLocal, init_db
import crud
from api_forms import on_new_response, job_config


# Test data - simulating Google Form responses
TEST_RESPONSES = [
    {
        "name": "Test Candidate Alpha",
        "email": "test.alpha@example.com",
        "phone": "+1234567890",
        "row_number": 100,
        "resume_filename_from_sheet": "test_alpha_resume.pdf",
    },
    {
        "name": "Test Candidate Beta",
        "email": "test.beta@example.com",
        "phone": "+1234567891",
        "row_number": 101,
        "resume_filename_from_sheet": "test_beta_resume.pdf",
    },
    {
        # DUPLICATE - same email as first candidate
        "name": "Test Candidate Alpha (Updated Name)",
        "email": "test.alpha@example.com",  # Same email!
        "phone": "+1234567892",
        "row_number": 102,
        "resume_filename_from_sheet": "test_alpha_updated_resume.pdf",
    },
]

# Dummy resume content (minimal PDF)
DUMMY_RESUME_PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000052 00000 n
0000000101 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
190
%%EOF
"""


async def test_duplicate_prevention():
    """Main test function"""
    print("=" * 80)
    print("TESTING DUPLICATE INTERVIEW PREVENTION")
    print("=" * 80)
    print()
    
    # Initialize database
    init_db()
    print("✅ Database initialized")
    print()
    
    # Set up test job
    test_job_id = "test_job_duplicate_prevention"
    job_config[test_job_id] = {
        "job_description": "Test job for duplicate prevention - looking for Python developers with 2+ years experience",
        "keywords": ["python", "developer"],
        "threshold": 50.0,  # Lower threshold so test resumes pass
        "calendar_id": "primary",
        "meeting_duration_minutes": 30,
        "interviewer_email": None,
    }
    
    # Create job in database
    db = SessionLocal()
    try:
        existing_job = crud.get_job(db, test_job_id)
        if existing_job:
            print(f"⚠️  Test job already exists, deleting...")
            crud.delete_job(db, test_job_id)
        
        job = crud.create_job(
            db=db,
            job_id=test_job_id,
            title="Test Job - Duplicate Prevention",
            description="This is a test job to verify duplicate interview prevention works correctly",
        )
        print(f"✅ Created test job: {job.title}")
        print()
    finally:
        db.close()
    
    # Test each response
    for i, response in enumerate(TEST_RESPONSES, 1):
        print("-" * 80)
        print(f"TEST {i}/3: Processing response from {response['name']}")
        print(f"  Email: {response['email']}")
        print(f"  Row: {response['row_number']}")
        print("-" * 80)
        
        # Check if candidate already exists (before processing)
        db = SessionLocal()
        try:
            existing = crud.get_candidate_by_email(db, test_job_id, response['email'])
            if existing:
                print(f"📋 Candidate already in database:")
                print(f"   ID: {existing.id}")
                print(f"   Name: {existing.name}")
                print(f"   Email: {existing.email}")
                print(f"   Applied: {existing.applied_at}")
                print(f"   ⚠️  EXPECTING: on_new_response should SKIP this candidate")
            else:
                print(f"📋 Candidate NOT in database yet")
                print(f"   ✅ EXPECTING: on_new_response should process and create candidate")
        finally:
            db.close()
        
        print()
        print("🔄 Calling on_new_response()...")
        print()
        
        # Call the callback (this is what happens when form watcher finds new response)
        try:
            await on_new_response(
                response=response,
                resume_bytes=DUMMY_RESUME_PDF,
                resume_filename="test_resume.pdf",
                job_id=test_job_id,
            )
        except Exception as e:
            print(f"❌ ERROR during processing: {e}")
            import traceback
            traceback.print_exc()
        
        print()
        
        # Check database after processing
        db = SessionLocal()
        try:
            candidate = crud.get_candidate_by_email(db, test_job_id, response['email'])
            if candidate:
                print(f"✅ Candidate NOW in database:")
                print(f"   ID: {candidate.id}")
                print(f"   Name: {candidate.name}")
                print(f"   Email: {candidate.email}")
                print(f"   Score: {candidate.score}")
                print(f"   Applied: {candidate.applied_at}")
                
                # Check if interview was scheduled
                interviews = db.query(crud.models.Interview).filter(
                    crud.models.Interview.candidate_id == candidate.id
                ).all()
                if interviews:
                    print(f"   Interviews scheduled: {len(interviews)}")
                    for interview in interviews:
                        print(f"     - ID: {interview.id}, Status: {interview.status}, Time: {interview.scheduled_start}")
                else:
                    print(f"   Interviews scheduled: 0")
            else:
                print(f"⚠️  Candidate NOT in database (may have been skipped)")
        finally:
            db.close()
        
        print()
        print()
    
    # Final summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    db = SessionLocal()
    try:
        all_candidates = crud.get_candidates_by_job(db, test_job_id)
        print(f"Total candidates in database for test job: {len(all_candidates)}")
        print()
        
        for candidate in all_candidates:
            interviews = db.query(crud.models.Interview).filter(
                crud.models.Interview.candidate_id == candidate.id
            ).all()
            print(f"  {candidate.name} ({candidate.email})")
            print(f"    Score: {candidate.score} | Interviews: {len(interviews)}")
        
        print()
        print("EXPECTED RESULTS:")
        print("  ✅ 2 candidates total (Alpha and Beta)")
        print("  ✅ Alpha should have 1 interview (not 2, even though submitted twice)")
        print("  ✅ Beta should have 1 interview")
        print("  ✅ Third submission (duplicate Alpha) should have been SKIPPED")
        print()
        
        # Verify expectations
        if len(all_candidates) == 2:
            print("✅ PASS: Correct number of candidates (2)")
            
            alpha_candidates = [c for c in all_candidates if c.email == "test.alpha@example.com"]
            beta_candidates = [c for c in all_candidates if c.email == "test.beta@example.com"]
            
            if len(alpha_candidates) == 1:
                print("✅ PASS: Only 1 Alpha candidate (duplicate was prevented)")
                
                alpha_interviews = db.query(crud.models.Interview).filter(
                    crud.models.Interview.candidate_id == alpha_candidates[0].id
                ).all()
                
                if len(alpha_interviews) <= 1:
                    print(f"✅ PASS: Alpha has {len(alpha_interviews)} interview(s) (no duplicates)")
                else:
                    print(f"❌ FAIL: Alpha has {len(alpha_interviews)} interviews (expected 1)")
            else:
                print(f"❌ FAIL: Found {len(alpha_candidates)} Alpha candidates (expected 1)")
            
            if len(beta_candidates) == 1:
                print("✅ PASS: Only 1 Beta candidate")
            else:
                print(f"❌ FAIL: Found {len(beta_candidates)} Beta candidates (expected 1)")
        else:
            print(f"❌ FAIL: Wrong number of candidates ({len(all_candidates)}, expected 2)")
        
    finally:
        db.close()
    
    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print()
    print("To clean up test data, run:")
    print(f"  cd backend")
    print(f"  sqlite3 intellimeet.db \"DELETE FROM candidates WHERE job_id='{test_job_id}'; DELETE FROM jobs WHERE id='{test_job_id}';\"")
    print()


if __name__ == "__main__":
    print()
    print("This script will test the duplicate interview prevention fix by:")
    print("  1. Creating a test job")
    print("  2. Processing 3 form responses (with 1 duplicate email)")
    print("  3. Verifying that duplicate is skipped")
    print()
    input("Press ENTER to start the test...")
    print()
    
    # Run async test
    asyncio.run(test_duplicate_prevention())
