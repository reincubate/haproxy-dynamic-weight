haproxy-dynamic-weight
======================

Dynamically set server weights in haproxy based on load.

## Rationale

`HAProxy` is a fine choice of load-balancer, but the balancing options it allows do not
including balancing work across servers according to their load. `haproxy-dynamic-weight`
provides a way to dynamically and automatically allocate work across servers in proportion
to their load to get the most from them.

The script was built at [Reincubate](http://www.reincubate.com) where its primary use has
been to reduce the load on virtual servers temporarily suffering from high CPU steal.

## Design principles

 * The script is an example of simplicity over configurability. Hack it if you need something different,
   or enhance it and submit a pull request.
 * We use Python with no dependancies other than `python-memcached`.
 * We wanted to avoid polling servers over HTTP. Each server can serve multiple sites, and a monitoring
   page didn't belong on any one site deployment. We didn't want a site deployment dedicated for providing
   performance data. We use `memcached` instead, as access to a `memcached` instance is cheaper than another
   HTTP request.
 * We rely on each web server regularly asking for the weight it wants (with `request-lb-weight.py`), placing
   that value in a low-TTL `memcached` store. The `HAProxy` server polls this and periodically adjusts weights
   as a consequence (with `set-lb-weight.py`).
 * We rely on the web servers to caculate their weight, rather than the `HAProxy` machine, as we may extend the
   weight calculation to include other web server-specific factors in future.
 * We base the weight calculation on the five minute load average of each web server, as we adjust weights each
   minute. If the measurement and the weight adjustment were both done over the same period we would see spikiness
   and undesirable behaviour in the weightings and performance.

## Installation & usage

We use `Puppet` to push `request-lb-weight.py` to our web servers and create a one-minute cronjob to run it
as a non-privileged user. We deploy and cron `set-lb-weight.py` in the same way on our load-balancers.

Both scripts take only a single argument, which is the hostname of the `memcached` server to use. If another
argument is provided, the script will report what it is doing. It will be silent otherwise.

`python-memcached` can be installed with `apt-get install python-memcache` on Ubuntu, or with `pip install python-memcached`.

### Requesting a server's weight

<pre><code>user@webserver-1:~# request-lb-weight.py memcached-1:11211</code></pre>

### Requesting a server's weight with debug output

<pre><code>user@webserver-1:~# request-lb-weight.py memcached-1:11211 debug
Declaring weight of 163 for webserver-1 for 120s, given load of 1.82</code></pre>

### Setting server weights

<pre><code>user@loadbalancer-1:~# set-lb-weight.py memcached-1:11211</code></pre>

### Setting server weights with debug output

<pre><code>user@loadbalancer-1:~# set-lb-weight.py memcached-1:11211 debug
Setting weights for site-1...
  - Changing webserver-1 from 148 to 170, 14.86%
  - Changing webserver-2 from 210 to 202, -3.81%
  - Changing webserver-3 from 176 to 184, 4.55%
Skipping site site-2; not all servers are reporting their weights
  - Running `echo "set weight site-1/webserver-1 148; set weight site-2/webserver-2 210; set weight site-3/webserver-3 176" | socat stdio /etc/haproxy/haproxy.sock`
</code></pre>

## See also

Before building this script we sought to find a pre-existing solution. There are a few similar scripts available
but none provided what we needed.

 * [Simple auto-scale with HAProxy](http://alex.cloudware.it/2011/10/simple-auto-scale-with-haproxy.html). This script is similar in that it can dynamically set HAProxy server weights. However:
   * It deals with spinning servers up and down which is beyond what we needed (and complicates the analysis challenge).
   * It determines server load by analysing a very small portion of the HAProxy logs. This is not a reliable dataset to analyse, as there are many reasons which might determine a server doing more or fewer requests: it being in multiple backends or frontends, the 15 log lines not being representative, it being loaded slightly more as a result of a balancer-based A/B test, it being in a sub-pool of servers dedicated to serving lighter requests.
   * It requires partial duplicate of HAProxy config in a `SERVERS` varable. [DRY](http://en.wikipedia.org/wiki/Don't_repeat_yourself).
 * [HAproxy Load Balancer Weight WatchDog](https://github.com/ssasso/lbwwd). A nice, simple Perl script. However:
 * * It relies on the load-balancer having to poll each server regularly, and each server making a load status page available. We did not want to do this.
