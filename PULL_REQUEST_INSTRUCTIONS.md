# Time Tracking Feature - Pull Request Instructions

## For Reviewers/Mergers

### Required Setup
After merging, anyone running the code must apply the database migration:

```bash
python manage.py migrate zerver 0778_task_time_log
```

### What This PR Adds
- **Task Time Tracking**: Start/stop timers for tasks
- **Time Logs**: View detailed work session history  
- **Statistics Dashboard**: Productivity insights and metrics
- **Database Migration**: Creates TaskTimeLog table (one-time setup)

### Backward Compatibility
- Existing task functionality works without migration
- Graceful degradation - time tracking shows friendly errors if migration not applied
- No breaking changes to current workflow

### Testing After Migration
1. Create or open a task
2. Click "Start" to begin time tracking
3. Click "Stop" to end tracking
4. Click "Logs" to view session history
5. Click "Time Stats" to see productivity dashboard

### Migration Details
- Migration file: `zerver/migrations/0778_task_time_log.py`
- Creates: `TaskTimeLog` model/table
- One-time setup per database
- Safe to run multiple times (Django handles idempotency)

### Error Handling
- 503 errors if migration not applied (graceful)
- No impact on existing task functionality
- Clear error messages guide users to run migration
