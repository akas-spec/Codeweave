with open('app/services/agent.py', 'r') as f:
    content = f.read()

old_workflow = '''Workflow:
1. First, understand the issue by searching the codebase.
2. Plan your fix step by step.
3. Create a branch for the fix.
4. Apply the patch(es).
5. Run tests to verify.
6. If tests fail, analyze the failure and retry (up to 3 attempts).
7. Once tests pass, commit, push, and create a PR.'''

new_workflow = '''Workflow:
1. First, understand the issue by searching the codebase.
2. Plan your fix step by step.
3. Apply the patch(es).
4. Run tests to verify.
5. Once tests pass and the task is complete, immediately call 'done'. (You may commit/push if explicitly asked).'''
content = content.replace(old_workflow, new_workflow)

old_done_rule = '''- TEST FAILURES: If a valid test run fails, inspect the failure. If the failure is unrelated to your patch/environment, call 'done' and report it. Retry only when the failure is actionable and reasonably fixable by you.'''
new_done_rule = '''- TEST FAILURES: If a valid test run fails, inspect the failure. If the failure is unrelated to your patch/environment, call 'done' and report it. Retry only when the failure is actionable and reasonably fixable by you.\n- DONE PREFERENCE: Once a relevant test passes and the requested task is satisfied, immediately call 'done'. Do not make unnecessary additional tool calls (like creating a branch or PR if not explicitly required).'''
content = content.replace(old_done_rule, new_done_rule)

old_dup = '''            # Check for repeated failed tool calls to prevent infinite loops
            is_duplicate = False
            for prev_tc in session.tool_calls:
                if prev_tc.tool == tool_name and prev_tc.args == tool_args and not prev_tc.success:
                    is_duplicate = True
                    break'''

new_dup = '''            # Check for repeated failed tool calls to prevent infinite loops
            is_duplicate = False
            
            # Find last successful repository state change
            last_state_change = -1
            for i, prev_tc in enumerate(session.tool_calls):
                if prev_tc.success and prev_tc.tool in ('apply_patch', 'git_ops'):
                    last_state_change = i
                    
            for i, prev_tc in enumerate(session.tool_calls):
                if prev_tc.tool == tool_name and prev_tc.args == tool_args and not prev_tc.success:
                    # If this is run_tests and the repo state changed since the failure, it's not a duplicate
                    if tool_name == 'run_tests' and last_state_change > i:
                        continue
                    is_duplicate = True
                    break'''
content = content.replace(old_dup, new_dup)

with open('app/services/agent.py', 'w') as f:
    f.write(content)
