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

def do_batch_update(db, table, cols, vals, batch_size=10000, sleep=0.1):
    validate(table)
    for col in cols:
        validate(col)
    stmt = '''
        UPDATE %s
        SET (%s) = (%s)
        WHERE id >= %%s AND id < %%s
    ''' % (table, ', '.join(cols), ', '.join(['%s'] * len(cols)))
    print stmt
    (min_id, max_id) = db.execute("SELECT MIN(id), MAX(id) FROM %s" % (table,))[0]
    if min_id is None:
        return

    print "%s rows need updating" % (max_id - min_id,)
    while min_id <= max_id:
        lower = min_id
        upper = min_id + batch_size
        print '%s about to update range [%s,%s)' % (time.asctime(), lower, upper)
        db.start_transaction()
        params = list(vals) + [lower, upper]
        db.execute(stmt, params=params)
        db.commit_transaction()
        min_id = upper
        time.sleep(sleep)

def add_bool_columns(db, table, cols):
    validate(table)
    for col in cols:
        validate(col)
    coltype = 'boolean'
    val = 'false'

    stmt = ('ALTER TABLE %s ' % (table,)) \
           + ', '.join(['ADD %s %s' % (col, coltype) for col in cols])
    timed_ddl(db, stmt)

    stmt = ('ALTER TABLE %s ' % (table,)) \
           + ', '.join(['ALTER %s SET DEFAULT %s' % (col, val) for col in cols])
    timed_ddl(db, stmt)

    vals = [val] * len(cols)
    do_batch_update(db, table, cols, vals)

    stmt = 'ANALYZE %s' % (table,)
    timed_ddl(db, stmt)

    stmt = ('ALTER TABLE %s ' % (table,)) \
           + ', '.join(['ALTER %s SET NOT NULL' % (col,) for col in cols])
    timed_ddl(db, stmt)
