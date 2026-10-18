#!/bin/sh
set -eu

# Insert before the VM's final REJECT rule. Check first so service restarts are safe.
if ! /usr/sbin/iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null; then
    /usr/sbin/iptables -I INPUT 1 -p tcp --dport 80 -j ACCEPT
fi
