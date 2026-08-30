import asyncio
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)

from app.services.agent import AgentOrchestrator, AgentSession
from app.tools.search_code import SearchCodeTool

class MockRepo:
    def __init__(self):
        self.id = 2
        self.full_name = 'nedbat/pkgsample'

class MockSearchCodeTool(SearchCodeTool):
    def __init__(self, *args, **kwargs):
        super().__init__(db=None, repository_id=2)
    
    async def execute(self, query: str, file_pattern: str = None, top_k: int = 5) -> str:
        # Instead of vector search, just return the add.py file
        return '''
Chunk 1
File: src/pkgsample/add.py
def add(x, y):
    return x - y
'''

async def test_agent():
    repo = MockRepo()
    repo_path = Path('./repos/nedbat_pkgsample')
    agent = AgentOrchestrator(
        db=None, 
        repository=repo,
        repo_path=repo_path,
        access_token=None
    )
    # Override search code tool
    agent._tools['search_code'] = MockSearchCodeTool(db=None, repository_id=repo.id)
    
    print('Starting Agent...')
    session = await agent.run(issue_description='The tests in tests/test_add.py are failing because the add function is implemented incorrectly. Please fix the add function in the source code so the tests pass. Do not modify the test files.')
    
    print('=== FINISHED ===')
    print('Status:', session.status)
    print('Summary:', session.summary)
    print('Tool calls:', len(session.tool_calls))
    for i, tc in enumerate(session.tool_calls):
        print(f'[{i}] {tc.tool}({tc.args}) -> success: {tc.success}')
    
if __name__ == '__main__':
    asyncio.run(test_agent())
