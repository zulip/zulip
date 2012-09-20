#!/bin/sh

error() {
  echo "Error"
  exit 1
}

TF="/tmp/test-concat.txt"

echo "concatfilepart"
echo

rm -r /tmp/test-concat.txt*

puppet concatfilepart1.pp
echo "ABC =? $(cat /tmp/test-concat.txt)"

puppet concatfilepart2.pp
echo "BC =? $(cat /tmp/test-concat.txt)"

puppet concatfilepart3.pp
echo "ZBC =? $(cat /tmp/test-concat.txt)"

puppet concatfilepart4.pp
echo " =? $(cat /tmp/test-concat.txt)"
