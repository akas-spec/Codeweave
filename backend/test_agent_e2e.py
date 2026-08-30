import urllib.request
import json
import time

def run():
    req = urllib.request.Request(
        'http://localhost:8000/api/agent/fix',
        data=json.dumps({
            'repository_id': 2,
            'issue_description': 'The tests in tests/test_add.py are failing because the add function is implemented incorrectly. Please fix the add function in the source code so the tests pass. Do not modify the test files.'
        }).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    print("Triggering agent fix...")
    with urllib.request.urlopen(req) as res:
        job = json.loads(res.read().decode('utf-8'))
        job_id = job['job_id']
        print(f"Started job {job_id}")

    # Poll status
    while True:
        time.sleep(5)
        status_req = urllib.request.Request(f'http://localhost:8000/api/agent/status/{job_id}')
        with urllib.request.urlopen(status_req) as res:
            status_data = json.loads(res.read().decode('utf-8'))
            status = status_data['status']
            print(f"Status: {status} (Iterations: {status_data.get('iterations', 0)})")
            if status in ['completed', 'failed', 'max_iterations_reached']:
                print("\nFinal Result:")
                print(f"Message: {status_data.get('message')}")
                tool_calls = status_data.get('tool_calls', [])
                print(f"Total Tool Calls: {len(tool_calls)}")
                for i, tc in enumerate(tool_calls):
                    print(f"[{i+1}] {tc.get('tool')}({tc.get('input')}) -> success: {tc.get('success')}")
                break

if __name__ == '__main__':
    run()
