#!/usr/bin/env zsh
# _cc3x3_resolve: a folder named outright under a root must work even with no .git/CLAUDE.md of its own
# (a workspace whose repos sit one level down), from any cwd, in any letter case, returning the on-disk spelling.
# Regression: `cc farfolio AutoApply-source` failed with "no project named" (2026-11-04).
emulate -L zsh
root=$(mktemp -d); trap 'rm -rf $root' EXIT
mkdir -p $root/Workspace-Src/inner/.git $root/real/.git
CC_ROOTS=($root); source ${0:A:h:h}/cc.zsh
cd /

fail=0
check() { local got=$(_cc3x3_resolve $1); [[ ${got:A} == ${2:A} || $got == $2 ]] && print "ok   $1" || { print "FAIL $1: got '$got', want '$2'"; fail=1 }; }
check Workspace-Src  $root:A/Workspace-Src   # no marker of its own
check workspace-src  $root:A/Workspace-Src   # wrong case still returns the real spelling
check real           $root:A/real            # normal project
check nosuch         ""                      # unknown name stays an error
check a/b            ""                      # relative paths are not looked up under the roots
exit $fail
