#!/usr/bin/env python

# Please note the LICENSE file accompanying this script.
# See https://github.com/reincubate/haproxy-dynamic-weight for more information.

import os, socket, sys, commands, memcache

# Let's find the current state of the load-balancer
SOCKET = '/etc/haproxy/haproxy.sock'
status = commands.getstatusoutput('echo "show stat" | socat %s stdio' % SOCKET )
lines = status[1].split('\n')
state, servers = {}, {}
debug = len(sys.argv) > 2

if len(sys.argv) < 2:
    raise Exception( 'You must pass the hostname and port of your memcached server' )

mc = memcache.Client( [ sys.argv[1] ], )

for l in lines:
    vals = l.split(',')

    if vals[0].startswith('#') or vals[0] == '':
        continue

    if vals[1] == 'FRONTEND':
        end = 'f'
        continue
    elif vals[1] == 'BACKEND':
        end = 'b'
        continue

    site, hostname, status, weight, code = vals[0], vals[1], vals[17], vals[18], vals[36]

    if site not in state:
        state[site] = {}

    state[site][hostname] = {
        'status': status,
        'weight': int(weight),
        'code': code,
    }

    if hostname not in servers: # Let's get an array of all the servers we need to know about
        servers[hostname] = mc.get( 'server-weight-%s' % hostname, ) # What does memcached say?

command = []

# Let's update the weights, but only where we have a weight for every server in the site
for site in state.keys():
    ok = True
    for hostname in state[site].keys():
        if hostname not in servers.keys() or not servers[hostname]:
            ok = False
            break

    if not ok:
        if debug: print 'Skipping site %s; not all servers are reporting their weights' % site
        continue

    if debug: print 'Setting weights for %s...' % site

    for hostname in state[site].keys():
        perc = ( 100.0 / state[site][hostname]['weight'] * servers[hostname] ) - 100.0
        if debug: print '  - Changing %s from %s to %s, %.2f%%' % ( hostname, state[site][hostname]['weight'], servers[hostname], perc )
        # Must stop this from adding disabled things back into the balance...
        command.append( 'set weight %s/%s %d' % ( site, hostname, servers[hostname], ) )

# Let's tell the load-balancer what to do
if command:
    if debug: print '  - Running `echo "%s" | socat stdio %s`' % ( '; '.join( command ), SOCKET )
    status = commands.getstatusoutput('echo "%s" | socat stdio %s' % ( '; '.join( command ), SOCKET ) )

    if status[1].strip():
        raise Exception( status[1] )