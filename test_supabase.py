import httpx

SUPABASE_URL = 'https://uvcqfhwcvxtasgokihic.supabase.co'
SERVICE_KEY = 'sb_secret_VgKGF55QQx6zwRB-ecHptg_b_FQ_TLY'
ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InV2Y3FmaHdjdnh0YXNnb2tpaGljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjU4OTM5MTMsImV4cCI6MjA4MTQ2OTkxM30.E7m_s-C5XzB2ZgiwewyBl8LwYr2rxa09txvky0kCVfI'

# Try to insert a test conversation to check if table exists
test_data = {
    "id": "00000000-0000-0000-0000-000000000001",
    "user_id": "test",
    "title": "Test",
    "messages": []
}

r = httpx.post(
    f'{SUPABASE_URL}/rest/v1/conversations',
    headers={
        'apikey': ANON_KEY,
        'Authorization': f'Bearer {ANON_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    },
    json=test_data,
    timeout=30
)

print(f'Status: {r.status_code}')
print(f'Response: {r.text}')

if r.status_code == 404:
    print('\nTable does not exist. Please create it manually in Supabase dashboard.')
elif r.status_code == 201:
    print('\nTable exists! Deleting test record...')
    # Delete the test record
    r2 = httpx.delete(
        f'{SUPABASE_URL}/rest/v1/conversations?id=eq.00000000-0000-0000-0000-000000000001',
        headers={
            'apikey': ANON_KEY,
            'Authorization': f'Bearer {ANON_KEY}'
        }
    )
    print(f'Delete status: {r2.status_code}')
