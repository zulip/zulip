import re
import time

def timed_ddl(db, stmt):
    print
    print time.asctime()
    print stmt
    t = time.time()
    db.execute(stmt)
    delay = time.time() - t
    print 'Took %.2fs' % (delay,)

def validate(sql_thingy):
    # Do basic validation that table/col name is safe.
    if not re.match('^[a-z][a-z\d_]+$', sql_thingy):
        raise Exception('Invalid SQL object: %s' % (sql_thingy,))

def do_batch_update(db, table, col, val, batch_size=10000, sleep=0.1):
    validate(table)
    validate(col)
    stmt = '''
        UPDATE %s
        SET %s = %%s
        WHERE id >= %%s AND id < %%s
    ''' % (table, col)
    (min_id, max_id) = db.execute("SELECT MIN(id), MAX(id) FROM %s" % (table,))[0]
    if min_id is None:
        return
    while min_id <= max_id:
        lower = min_id
        upper = min_id + batch_size
        print '%s about to update range [%s,%s)' % (time.asctime(), lower, upper)
        db.start_transaction()
        db.execute(stmt, params=[val, lower, upper])
        db.commit_transaction()
        min_id = upper
        time.sleep(sleep)

def add_bool_column(db, table, col):
    validate(table)
    validate(col)
    coltype = 'boolean'
    val = 'false'

    stmt = 'ALTER TABLE %s ADD %s %s' % (table, col, coltype)
    timed_ddl(db, stmt)

    stmt = 'ALTER TABLE %s ALTER %s SET DEFAULT %s' % (table, col, val)
    timed_ddl(db, stmt)

    do_batch_update(db, table, col, val)

    stmt = 'ANALYZE %s' % (table,)
    timed_ddl(db, stmt)

    stmt = 'ALTER TABLE %s ALTER %s SET NOT NULL' % (table, col)
    timed_ddl(db, stmt)
