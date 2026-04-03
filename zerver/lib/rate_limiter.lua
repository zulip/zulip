-- GCRA (Generic Cell Rate Algorithm) rate limiter.
-- Atomically checks all rules and updates TATs in a single round trip.
--
-- KEYS[1] = block_key, KEYS[2] = gcra_key
-- ARGV[1] = num_rules, ARGV[2..2*num_rules+1] = w1, l1, w2, l2, ...
-- ARGV[2*num_rules+2] (optional) = override timestamp for tests only
--
-- Returns a 4-element list of strings:
--   [ratelimited, secs_to_freedom, calls_remaining, secs_to_reset]

local block_key = KEYS[1]
local gcra_key = KEYS[2]
local num_rules = tonumber(ARGV[1])

-- Use Redis server time so that all app servers see a consistent
-- clock, avoiding false positives from inter-machine clock drift.
-- Tests may pass an explicit timestamp as the last argument to get
-- deterministic behavior without wall-clock sleeps.
local now
local test_time_arg = ARGV[2 * num_rules + 2]
if test_time_arg then
    now = tonumber(test_time_arg)
else
    local time_result = redis.call('TIME')
    now = tonumber(time_result[1]) + tonumber(time_result[2]) / 1000000
end

-- Check for manual block (set by block_access).
if redis.call('EXISTS', block_key) == 1 then
    local ttl = redis.call('PTTL', block_key)
    if ttl < 0 then ttl = 1000 end
    return {'1', string.format('%.17g', ttl / 1000.0), '0', '0'}
end

-- For each rule, compute the new TAT (Theoretical Arrival Time)
-- without writing anything yet.  If any rule would be violated,
-- we reject the request and leave all TATs unchanged.
local fields = {}
local new_tats = {}
local max_ttl = 0
local limited = false
local secs_to_freedom = 0

for i = 1, num_rules do
    local window = tonumber(ARGV[1 + (i - 1) * 2 + 1])
    local limit = tonumber(ARGV[1 + (i - 1) * 2 + 2])
    local field = window .. ':' .. limit
    -- Time between ideally-spaced requests.
    local emission_interval = window / limit

    local stored = redis.call('HGET', gcra_key, field)
    -- If the stored TAT is in the past, treat it as now (the
    -- bucket has fully drained).
    local tat = math.max(stored and tonumber(stored) or now, now)
    local new_tat = tat + emission_interval

    -- The bucket overflows when new_tat exceeds the window
    -- horizon: the request arrived faster than the drain rate
    -- can sustain.
    if new_tat > now + window then
        limited = true
        local freedom = new_tat - window - now
        if freedom > secs_to_freedom then
            secs_to_freedom = freedom
        end
    end

    fields[i] = field
    new_tats[i] = new_tat
    local remaining = new_tat - now
    if remaining > max_ttl then
        max_ttl = remaining
    end
end

-- All-or-nothing: if any rule triggered, reject without updating.
if limited then
    return {'1', string.format('%.17g', secs_to_freedom), '0', '0'}
end

-- Request allowed — persist all new TATs atomically.
for i = 1, num_rules do
    redis.call('HSET', gcra_key, fields[i], string.format('%.17g', new_tats[i]))
end
local ttl_seconds = math.ceil(max_ttl)
if ttl_seconds > 0 then
    redis.call('EXPIRE', gcra_key, ttl_seconds)
end

-- Compute remaining quota for the max (outermost) rule, used for
-- the X-RateLimit-Remaining response header.
local max_window = tonumber(ARGV[1 + (num_rules - 1) * 2 + 1])
local max_limit = tonumber(ARGV[1 + (num_rules - 1) * 2 + 2])
local max_tat = new_tats[num_rules]
local calls_remaining = math.max(0, math.floor(
    (now + max_window - max_tat) * max_limit / max_window
))
local secs_to_reset = max_tat - now

return {'0', '0', tostring(calls_remaining), string.format('%.17g', secs_to_reset)}
