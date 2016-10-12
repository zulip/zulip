#!/usr/bin/env perl
# -*-mode:cperl; indent-tabs-mode: nil-*-

## Perform many different checks against Postgres databases.
## Designed primarily as a Nagios script.
## Run with --help for a summary.
##
## Greg Sabino Mullane <greg@endpoint.com>
## End Point Corporation http://www.endpoint.com/
## BSD licensed, see complete license at bottom of this script
## The latest version can be found at:
## http://www.bucardo.org/check_postgres/
##
## See the HISTORY section for other contributors

package check_postgres;

use 5.006001;
use strict;
use warnings;
use utf8;
use Getopt::Long qw/GetOptions/;
Getopt::Long::Configure(qw/ no_ignore_case pass_through  /);
use File::Basename qw/basename/;
use File::Temp qw/tempfile tempdir/;
File::Temp->safe_level( File::Temp::MEDIUM );
use Cwd;
use Data::Dumper qw/Dumper/;
$Data::Dumper::Varname = 'POSTGRES';
$Data::Dumper::Indent = 2;
$Data::Dumper::Useqq = 1;

binmode STDOUT, ':encoding(UTF-8)';

our $VERSION = '2.22.0';

use vars qw/ %opt $PGBINDIR $PSQL $res $COM $SQL $db /;

## Which user to connect as if --dbuser is not given
$opt{defaultuser} = 'postgres';

## Which port to connect to if --dbport is not given
$opt{defaultport} = 5432;

## What type of output to use by default
our $DEFAULT_OUTPUT = 'nagios';

## If psql binaries are not in your path, it is recommended to hardcode it here,
## as an alternative to the --PGBINDIR option
$PGBINDIR = '';

## If this is true, $opt{PSQL} and $opt{PGBINDIR} are disabled for security reasons
our $NO_PSQL_OPTION = 1;

## If true, we show how long each query took by default. Requires Time::HiRes to be installed.
$opt{showtime} = 1;

## If true, we show "after the pipe" statistics
$opt{showperf} = 1;

## Default time display format, used for last_vacuum and last_analyze
our $SHOWTIME = 'HH24:MI FMMonth DD, YYYY';

## Always prepend 'postgres_' to the name of the service in the output string
our $FANCYNAME = 1;

## Change the service name to uppercase
our $YELLNAME = 1;

## Preferred order of ways to fetch pages for new_version checks
our $get_method_timeout = 30;
our @get_methods = (
    "GET -t $get_method_timeout -H 'Pragma: no-cache'",
    "wget --quiet --timeout=$get_method_timeout --no-cache -O -",
    "curl --silent --max-time $get_method_timeout -H 'Pragma: no-cache'",
    "fetch -q -T $get_method_timeout -o -",
    "lynx --connect-timeout=$get_method_timeout --dump",
    'links -dump',
);

## Nothing below this line should need to be changed for normal usage.
## If you do find yourself needing to change something,
## please email the author as it probably indicates something
## that could be made into a command-line option or moved above.

## Messages. Translations always welcome
## Items without a leading tab still need translating
## no critic (RequireInterpolationOfMetachars)
our %msg = (
'en' => {
    'address'            => q{address},
    'age'                => q{age},
    'backends-fatal'     => q{Could not connect: too many connections},
    'backends-mrtg'      => q{DB=$1 Max connections=$2},
    'backends-msg'       => q{$1 of $2 connections ($3%)},
    'backends-nomax'     => q{Could not determine max_connections},
    'backends-oknone'    => q{No connections},
    'backends-po'        => q{sorry, too many clients already},
    'backends-users'     => q{$1 for number of users must be a number or percentage},
    'bloat-index'        => q{(db $1) index $2 rows:$3 pages:$4 shouldbe:$5 ($6X) wasted bytes:$7 ($8)},
    'bloat-nomin'        => q{no relations meet the minimum bloat criteria},
    'bloat-table'        => q{(db $1) table $2.$3 rows:$4 pages:$5 shouldbe:$6 ($7X) wasted size:$8 ($9)},
    'bug-report'         => q{Please report these details to check_postgres@bucardo.org:},
    'checkcluster-id'    => q{Database system identifier:},
    'checkcluster-msg'   => q{cluster_id: $1},
    'checkcluster-nomrtg'=> q{Must provide a number via the --mrtg option},
    'checkmode-prod'     => q{in production},
    'checkmode-recovery' => q{in archive recovery},
    'checkmode-state'    => q{Database cluster state:},
    'checkpoint-baddir'  => q{Invalid data_directory: "$1"},
    'checkpoint-baddir2' => q{pg_controldata could not read the given data directory: "$1"},
    'checkpoint-badver'  => q{Failed to run pg_controldata - probably the wrong version ($1)},
    'checkpoint-badver2' => q{Failed to run pg_controldata - is it the correct version?},
    'checkpoint-nodir'   => q{Must supply a --datadir argument or set the PGDATA environment variable},
    'checkpoint-nodp'    => q{Must install the Perl module Date::Parse to use the checkpoint action},
    'checkpoint-noparse' => q{Unable to parse pg_controldata output: "$1"},
    'checkpoint-noregex' => q{Unable to find the regex for this check},
    'checkpoint-nosys'   => q{Could not call pg_controldata: $1},
    'checkpoint-ok'      => q{Last checkpoint was 1 second ago},
    'checkpoint-ok2'     => q{Last checkpoint was $1 seconds ago},
    'checkpoint-po'      => q{Time of latest checkpoint:},
    'checksum-msg'       => q{checksum: $1},
    'checksum-nomd'      => q{Must install the Perl module Digest::MD5 to use the checksum action},
    'checksum-nomrtg'    => q{Must provide a checksum via the --mrtg option},
    'custom-invalid'     => q{Invalid format returned by custom query},
    'custom-norows'      => q{No rows returned},
    'custom-nostring'    => q{Must provide a query string},
    'database'           => q{database},
    'dbsize-version'     => q{Target database must be version 8.1 or higher to run the database_size action},
    'depr-pgcontroldata' => q{PGCONTROLDATA is deprecated, use PGBINDIR instead.},
    'die-action-version' => q{Cannot run "$1": server version must be >= $2, but is $3},
    'die-badtime'        => q{Value for '$1' must be a valid time. Examples: -$2 1s  -$2 "10 minutes"},
    'die-badversion'     => q{Invalid version string: $1},
    'die-noset'          => q{Cannot run "$1" $2 is not set to on},
    'die-nosetting'      => q{Could not fetch setting '$1'},
    'diskspace-fail'     => q{Invalid result from command "$1": $2},
    'diskspace-msg'      => q{FS $1 mounted on $2 is using $3 of $4 ($5%)},
    'diskspace-nodata'   => q{Could not determine data_directory: are you connecting as a superuser?},
    'diskspace-nodf'     => q{Could not find required executable /bin/df},
    'diskspace-nodir'    => q{Could not find data directory "$1"},
    'file-noclose'       => q{Could not close $1: $2},
    'files'              => q{files},
    'fsm-page-highver'   => q{Cannot check fsm_pages on servers version 8.4 or greater},
    'fsm-page-msg'       => q{fsm page slots used: $1 of $2 ($3%)},
    'fsm-rel-highver'    => q{Cannot check fsm_relations on servers version 8.4 or greater},
    'fsm-rel-msg'        => q{fsm relations used: $1 of $2 ($3%)},
    'hs-future-replica'  => q{Slave reporting master server clock is ahead, check time sync},
    'hs-no-role'         => q{Not a master/slave couple},
    'hs-no-location'     => q{Could not get current xlog location on $1},
    'hs-receive-delay'   => q{receive-delay},
    'hs-replay-delay'    => q{replay_delay},
    'hs-time-delay'      => q{time_delay},
    'hs-time-version'    => q{Database must be version 9.1 or higher to check slave lag by time},
    'index'              => q{Index},
    'invalid-option'     => q{Invalid option},
    'invalid-query'      => q{Invalid query returned: $1},
    'language'           => q{Language},
    'listener-msg'       => q{listeners found: $1},
    'listening'          => q{listening},
    'locks-msg'          => q{total "$1" locks: $2},
    'locks-msg2'         => q{total locks: $1},
    'logfile-bad'        => q{Invalid logfile "$1"},
    'logfile-debug'      => q{Final logfile: $1},
    'logfile-dne'        => q{logfile $1 does not exist!},
    'logfile-fail'       => q{fails logging to: $1},
    'logfile-ok'         => q{logs to: $1},
    'logfile-openfail'   => q{logfile "$1" failed to open: $2},
    'logfile-opt-bad'    => q{Invalid logfile option},
    'logfile-seekfail'   => q{Seek on $1 failed: $2},
    'logfile-stderr'     => q{Logfile output has been redirected to stderr: please provide a filename},
    'logfile-syslog'     => q{Database is using syslog, please specify path with --logfile option (fac=$1)},
    'mode-standby'       => q{Server in standby mode},
    'mode'               => q{mode},
    'mrtg-fail'          => q{Action $1 failed: $2},
    'new-ver-nocver'     => q{Could not download version information for $1},
    'new-ver-badver'     => q{Could not parse version information for $1},
    'new-ver-dev'        => q{Cannot compare versions on development versions: you have $1 version $2},
    'new-ver-nolver'     => q{Could not determine local version information for $1},
    'new-ver-ok'         => q{Version $1 is the latest for $2},
    'new-ver-warn'       => q{Please upgrade to version $1 of $2. You are running $3},
    'new-ver-tt'         => q{Your version of $1 ($2) appears to be ahead of the current release! ($3)},
    'no-db'              => q{No databases},
    'no-match-db'        => q{No matching databases found due to exclusion/inclusion options},
    'no-match-fs'        => q{No matching file systems found due to exclusion/inclusion options},
    'no-match-rel'       => q{No matching relations found due to exclusion/inclusion options},
    'no-match-set'       => q{No matching settings found due to exclusion/inclusion options},
    'no-match-table'     => q{No matching tables found due to exclusion/inclusion options},
    'no-match-user'      => q{No matching entries found due to user exclusion/inclusion options},
    'no-parse-psql'      => q{Could not parse psql output!},
    'no-time-hires'      => q{Cannot find Time::HiRes, needed if 'showtime' is true},
    'opt-output-invalid' => q{Invalid output: must be 'nagios' or 'mrtg' or 'simple' or 'cacti'},
    'opt-psql-badpath'   => q{Invalid psql argument: must be full path to a file named psql},
    'opt-psql-noexec'    => q{The file "$1" does not appear to be executable},
    'opt-psql-noexist'   => q{Cannot find given psql executable: $1},
    'opt-psql-nofind'    => q{Could not find a suitable psql executable},
    'opt-psql-nover'     => q{Could not determine psql version},
    'opt-psql-restrict'  => q{Cannot use the --PGBINDIR or --PSQL option when NO_PSQL_OPTION is on},
    'pgagent-jobs-ok'    => q{No failed jobs},
    'pgbouncer-pool'     => q{Pool=$1 $2=$3},
    'pgb-backends-mrtg'  => q{DB=$1 Max connections=$2},
    'pgb-backends-msg'   => q{$1 of $2 connections ($3%)},
    'pgb-backends-none'  => q{No connections},
    'pgb-backends-users' => q{$1 for number of users must be a number or percentage},
    'PID'                => q{PID},
    'port'               => q{port},
    'preptxn-none'       => q{No prepared transactions found},
    'psa-disabled'       => q{No queries - is stats_command_string or track_activities off?},
    'psa-noexact'        => q{Unknown error},
    'psa-nosuper'        => q{No matches - please run as a superuser},
    'qtime-count-msg'    => q{Total queries: $1},
    'qtime-count-none'   => q{not more than $1 queries},
    'qtime-for-msg'      => q{$1 queries longer than $2s, longest: $3s$4 $5},
    'qtime-msg'          => q{longest query: $1s$2 $3},
    'qtime-none'         => q{no queries},
    'query'              => q{query},
    'queries'            => q{queries},
    'query-time'         => q{query_time},
    'range-badcs'        => q{Invalid '$1' option: must be a checksum},
    'range-badlock'      => q{Invalid '$1' option: must be number of locks, or "type1=#:type2=#"},
    'range-badpercent'   => q{Invalid '$1' option: must be a percentage},
    'range-badpercsize'  => q{Invalid '$1' option: must be a size or a percentage},
    'range-badsize'      => q{Invalid size for '$1' option},
    'range-badtype'      => q{validate_range called with unknown type '$1'},
    'range-badversion'   => q{Invalid string for '$1' option: $2},
    'range-cactionly'    => q{This action is for cacti use only and takes no warning or critical arguments},
    'range-int'          => q{Invalid argument for '$1' option: must be an integer},
    'range-int-pos'      => q{Invalid argument for '$1' option: must be a positive integer},
    'range-neg-percent'  => q{Cannot specify a negative percentage!},
    'range-none'         => q{No warning or critical options are needed},
    'range-noopt-both'   => q{Must provide both 'warning' and 'critical' options},
    'range-noopt-one'    => q{Must provide a 'warning' or 'critical' option},
    'range-noopt-only'   => q{Can only provide 'warning' OR 'critical' option},
    'range-noopt-orboth' => q{Must provide a 'warning' option, a 'critical' option, or both},
    'range-noopt-size'   => q{Must provide a warning and/or critical size},
    'range-nosize'       => q{Must provide a warning and/or critical size},
    'range-notime'       => q{Must provide a warning and/or critical time},
    'range-seconds'      => q{Invalid argument to '$1' option: must be number of seconds},
    'range-version'      => q{must be in the format X.Y or X.Y.Z, where X is the major version number, },
    'range-warnbig'      => q{The 'warning' option cannot be greater than the 'critical' option},
    'range-warnbigsize'  => q{The 'warning' option ($1 bytes) cannot be larger than the 'critical' option ($2 bytes)},
    'range-warnbigtime'  => q{The 'warning' option ($1 s) cannot be larger than the 'critical' option ($2 s)},
    'range-warnsmall'    => q{The 'warning' option cannot be less than the 'critical' option},
    'range-nointfortime' => q{Invalid argument for '$1' options: must be an integer, time or integer for time},
    'relsize-msg-ind'    => q{largest index is "$1": $2},
    'relsize-msg-reli'   => q{largest relation is index "$1": $2},
    'relsize-msg-relt'   => q{largest relation is table "$1": $2},
    'relsize-msg-tab'    => q{largest table is "$1": $2},
    'rep-badarg'         => q{Invalid repinfo argument: expected 6 comma-separated values},
    'rep-duh'            => q{Makes no sense to test replication with same values},
    'rep-fail'           => q{Row not replicated to slave $1},
    'rep-noarg'          => q{Need a repinfo argument},
    'rep-norow'          => q{Replication source row not found: $1},
    'rep-noslaves'       => q{No slaves found},
    'rep-notsame'        => q{Cannot test replication: values are not the same},
    'rep-ok'             => q{Row was replicated},
    'rep-sourcefail'     => q{Source update failed},
    'rep-timeout'        => q{Row was not replicated. Timeout: $1},
    'rep-unknown'        => q{Replication check failed},
    'rep-wrongvals'      => q{Cannot test replication: values are not the right ones ('$1' not '$2' nor '$3')},
    'runcommand-err'     => q{Unknown error inside of the "run_command" function},
    'runcommand-nodb'    => q{No target databases could be found},
    'runcommand-nodupe'  => q{Could not dupe STDERR},
    'runcommand-noerr'   => q{Could not open STDERR?!},
    'runcommand-nosys'   => q{System call failed with a $1},
    'runcommand-pgpass'  => q{Created temporary pgpass file $1},
    'runcommand-timeout' => q{Command timed out! Consider boosting --timeout higher than $1},
    'runtime-badmrtg'    => q{invalid queryname?},
    'runtime-badname'    => q{Invalid queryname option: must be a simple view name},
    'runtime-msg'        => q{query runtime: $1 seconds},
    'schema'             => q{Schema},
    'ss-createfile'      => q{Created file $1},
    'ss-different'       => q{"$1" is different:},
    'ss-existson'        => q{Exists on:},
    'ss-failed'          => q{Databases were different. Items not matched: $1},
    'ss-matched'         => q{All databases have identical items},
    'ss-missingon'       => q{Missing on:},
    'ss-noexist'         => q{$1 "$2" does not exist on all databases:},
    'ss-notset'          => q{"$1" is not set on all databases:},
    'ss-suffix'          => q{Error: cannot use suffix unless looking at time-based schemas},
    'seq-die'            => q{Could not determine information about sequence $1},
    'seq-msg'            => q{$1=$2% (calls left=$3)},
    'seq-none'           => q{No sequences found},
    'size'               => q{size},
    'slony-noschema'     => q{Could not determine the schema for Slony},
    'slony-nonumber'     => q{Call to sl_status did not return a number},
    'slony-lagtime'      => q{Slony lag time: $1},
    'symlink-create'     => q{Created "$1"},
    'symlink-done'       => q{Not creating "$1": $2 already linked to "$3"},
    'symlink-exists'     => q{Not creating "$1": $2 file already exists},
    'symlink-fail1'      => q{Failed to unlink "$1": $2},
    'symlink-fail2'      => q{Could not symlink $1 to $2: $3},
    'symlink-name'       => q{This command will not work unless the program has the word "postgres" in it},
    'symlink-unlink'     => q{Unlinking "$1":$2 },
    'table'              => q{Table},
    'testmode-end'       => q{END OF TEST MODE},
    'testmode-fail'      => q{Connection failed: $1 $2},
    'testmode-norun'     => q{Cannot run "$1" on $2: version must be >= $3, but is $4},
    'testmode-noset'     => q{Cannot run "$1" on $2: $3 is not set to on},
    'testmode-nover'     => q{Could not find version for $1},
    'testmode-ok'        => q{Connection ok: $1},
    'testmode-start'     => q{BEGIN TEST MODE},
    'time-day'           => q{day},
    'time-days'          => q{days},
    'time-hour'          => q{hour},
    'time-hours'         => q{hours},
    'time-minute'        => q{minute},
    'time-minutes'       => q{minutes},
    'time-month'         => q{month},
    'time-months'        => q{months},
    'time-second'        => q{second},
    'time-seconds'       => q{seconds},
    'time-week'          => q{week},
    'time-weeks'         => q{weeks},
    'time-year'          => q{year},
    'time-years'         => q{years},
    'timesync-diff'      => q{diff},
    'timesync-msg'       => q{timediff=$1 DB=$2 Local=$3},
    'transactions'       => q{transactions},
    'trigger-msg'        => q{Disabled triggers: $1},
    'txn-time'           => q{transaction_time},
    'txnidle-count-msg'  => q{Total idle in transaction: $1},
    'txnidle-count-none' => q{not more than $1 idle in transaction},
    'txnidle-for-msg'    => q{$1 idle transactions longer than $2s, longest: $3s$4 $5},
    'txnidle-msg'        => q{longest idle in txn: $1s$2 $3},
    'txnidle-none'       => q{no idle in transaction},
    'txntime-count-msg'  => q{Total transactions: $1},
    'txntime-count-none' => q{not more than $1 transactions},
    'txntime-for-msg'    => q{$1 transactions longer than $2s, longest: $3s$4 $5},
    'txntime-msg'        => q{longest txn: $1s$2 $3},
    'txntime-none'       => q{No transactions},
    'txnwrap-cbig'       => q{The 'critical' value must be less than 2 billion},
    'txnwrap-wbig'       => q{The 'warning' value must be less than 2 billion},
    'unknown-error'      => q{Unknown error},
    'usage'              => qq{\nUsage: \$1 <options>\n Try "\$1 --help" for a complete list of options\n Try "\$1 --man" for the full manual\n},
    'user'               => q{User},
    'username'           => q{username},
    'vac-nomatch-a'      => q{No matching tables have ever been analyzed},
    'vac-nomatch-v'      => q{No matching tables have ever been vacuumed},
    'version'            => q{version $1},
    'version-badmrtg'    => q{Invalid mrtg version argument},
    'version-fail'       => q{version $1, but expected $2},
    'version-ok'         => q{version $1},
    'wal-numfound'       => q{WAL files found: $1},
    'wal-numfound2'      => q{WAL "$2" files found: $1},
},
'fr' => {
    'address'            => q{adresse},
    'age'                => q{âge},
    'backends-fatal'     => q{N'a pas pu se connecter : trop de connexions},
    'backends-mrtg'      => q{DB=$1 Connexions maximum=$2},
    'backends-msg'       => q{$1 connexions sur $2 ($3%)},
    'backends-nomax'     => q{N'a pas pu déterminer max_connections},
    'backends-oknone'    => q{Aucune connexion},
    'backends-po'        => q{désolé, trop de clients sont déjà connectés},
    'backends-users'     => q{$1 pour le nombre d'utilisateurs doit être un nombre ou un pourcentage},
    'bloat-index'        => q{(db $1) index $2 lignes:$3 pages:$4 devrait être:$5 ($6X) octets perdus:$7 ($8)},
    'bloat-nomin'        => q{aucune relation n'atteint le critère minimum de fragmentation},
    'bloat-table'        => q{(db $1) table $2.$3 lignes:$4 pages:$5 devrait être:$6 ($7X) place perdue:$8 ($9)},
    'bug-report'         => q{Merci de rapporter ces d??tails ?? check_postgres@bucardo.org:},
    'checkcluster-id'    => q{Identifiant système de la base de données :},
    'checkcluster-msg'   => q{cluster_id : $1},
    'checkcluster-nomrtg'=> q{Doit fournir un numéro via l'option --mrtg},
    'checkmode-prod'     => q{en production},
    'checkmode-recovery' => q{en restauration d'archives},
    'checkmode-state'    => q{État de l'instance :},
    'checkpoint-baddir'  => q{data_directory invalide : "$1"},
    'checkpoint-baddir2' => q{pg_controldata n'a pas pu lire le répertoire des données indiqué : « $1 »},
    'checkpoint-badver'  => q{Échec lors de l'exécution de pg_controldata - probablement la mauvaise version ($1)},
    'checkpoint-badver2' => q{Échec lors de l'exécution de pg_controldata - est-ce la bonne version ?},
    'checkpoint-nodir'   => q{Vous devez fournir un argument --datadir ou configurer la variable d'environnement PGDATA},
    'checkpoint-nodp'    => q{Vous devez installer le module Perl Date::Parse pour utiliser l'action checkpoint},
    'checkpoint-noparse' => q{Incapable d'analyser le résultat de la commande pg_controldata : "$1"},
    'checkpoint-noregex' => q{La regex pour ce test n'a pas été trouvée},
    'checkpoint-nosys'   => q{N'a pas pu appeler pg_controldata : $1},
    'checkpoint-ok'      => q{Le dernier CHECKPOINT est survenu il y a une seconde},
    'checkpoint-ok2'     => q{Le dernier CHECKPOINT est survenu il y a $1 secondes},
    'checkpoint-po'      => q{Heure du dernier point de contrôle :},
    'checksum-msg'       => q{somme de contrôle : $1},
    'checksum-nomd'      => q{Vous devez installer le module Perl Digest::MD5 pour utiliser l'action checksum},
    'checksum-nomrtg'    => q{Vous devez fournir une somme de contrôle avec l'option --mrtg},
    'custom-invalid'     => q{Format invalide renvoyé par la requête personnalisée},
    'custom-norows'      => q{Aucune ligne renvoyée},
    'custom-nostring'    => q{Vous devez fournir une requête},
    'database'           => q{base de données},
    'dbsize-version'     => q{La base de données cible doit être une version 8.1 ou ultérieure pour exécuter l'action database_size},
'depr-pgcontroldata' => q{PGCONTROLDATA is deprecated, use PGBINDIR instead.},
    'die-action-version' => q{Ne peut pas exécuter « $1 » : la version du serveur doit être supérieure ou égale à $2, alors qu'elle est $3},
    'die-badtime'        => q{La valeur de « $1 » doit être une heure valide. Par exemple, -$2 1s  -$2 « 10 minutes »},
    'die-badversion'     => q{Version invalide : $1},
    'die-noset'          => q{Ne peut pas exécuter « $1 » $2 n'est pas activé},
    'die-nosetting'      => q{N'a pas pu récupérer le paramètre « $1 »},
    'diskspace-fail'     => q{Résultat invalide pour la commande « $1 » : $2},
    'diskspace-msg'      => q{Le système de fichiers $1 monté sur $2 utilise $3 sur $4 ($5%)},
    'diskspace-nodata'   => q{N'a pas pu déterminer data_directory : êtes-vous connecté en tant que super-utilisateur ?},
    'diskspace-nodf'     => q{N'a pas pu trouver l'exécutable /bin/df},
    'diskspace-nodir'    => q{N'a pas pu trouver le répertoire des données « $1 »},
    'files'              => q{fichiers},
    'file-noclose'       => q{N'a pas pu fermer $1 : $2},
    'fsm-page-highver'   => q{Ne peut pas vérifier fsm_pages sur des serveurs en version 8.4 ou ultérieure},
    'fsm-page-msg'       => q{emplacements de pages utilisés par la FSM : $1 sur $2 ($3%)},
    'fsm-rel-highver'    => q{Ne peut pas vérifier fsm_relations sur des serveurs en version 8.4 ou ultérieure},
    'fsm-rel-msg'        => q{relations tracées par la FSM : $1 sur $2 ($3%)},
'hs-future-replica'  => q{Slave reporting master server clock is ahead, check time sync},
    'hs-no-role'         => q{Pas de couple ma??tre/esclave},
    'hs-no-location'     => q{N'a pas pu obtenir l'emplacement courant dans le journal des transactions sur $1},
    'hs-receive-delay'   => q{délai de réception},
    'hs-replay-delay'    => q{délai de rejeu},
'hs-time-delay'      => q{time_delay},
'hs-time-version'    => q{Database must be version 9.1 or higher to check slave lag by time},
    'index'              => q{Index},
    'invalid-option'     => q{Option invalide},
    'invalid-query'      => q{Une requête invalide a renvoyé : $1},
    'language'           => q{Langage},
    'listener-msg'       => q{processus LISTEN trouvés : $1},
    'listening'          => q{en écoute},
    'locks-msg'          => q{total des verrous « $1 » : $2},
    'locks-msg2'         => q{total des verrous : $1},
    'logfile-bad'        => q{Option logfile invalide « $1 »},
    'logfile-debug'      => q{Journal applicatif final : $1},
    'logfile-dne'        => q{le journal applicatif $1 n'existe pas !},
    'logfile-fail'       => q{échec pour tracer dans : $1},
    'logfile-ok'         => q{trace dans : $1},
    'logfile-openfail'   => q{échec pour l'ouverture du journal applicatif « $1 » : $2},
    'logfile-opt-bad'    => q{Option logfile invalide},
    'logfile-seekfail'   => q{Échec de la recherche dans $1 : $2},
    'logfile-stderr'     => q{La sortie des traces a été redirigés stderr : merci de fournir un nom de fichier},
    'logfile-syslog'     => q{La base de données utiliser syslog, merci de spécifier le chemin avec l'option --logfile (fac=$1)},
    'mode-standby'       => q{Serveur en mode standby},
    'mode'               => q{mode},
    'mrtg-fail'          => q{Échec de l'action $1 : $2},
    'new-ver-nocver'     => q{N'a pas pu t??l??charger les informations de version pour $1},
    'new-ver-badver'     => q{N'a pas pu analyser les informations de version pour $1},
    'new-ver-dev'        => q{Ne peut pas comparer les versions sur des versions de d??veloppement : vous avez $1 version $2},
    'new-ver-nolver'     => q{N'a pas pu d??terminer les informations de version locale pour $1},
    'new-ver-ok'         => q{La version $1 est la dernière pour $2},
    'new-ver-warn'       => q{Merci de mettre à jour vers la version $1 de $2. Vous utilisez actuellement la $3},
    'new-ver-tt'         => q{Votre version de $1 ($2) semble ult??rieure ?? la version courante ! ($3)},
    'no-db'              => q{Pas de bases de données},
    'no-match-db'        => q{Aucune base de données trouvée à cause des options d'exclusion/inclusion},
    'no-match-fs'        => q{Aucun système de fichier trouvé à cause des options d'exclusion/inclusion},
    'no-match-rel'       => q{Aucune relation trouvée à cause des options d'exclusion/inclusion},
    'no-match-set'       => q{Aucun paramètre trouvé à cause des options d'exclusion/inclusion},
    'no-match-table'     => q{Aucune table trouvée à cause des options d'exclusion/inclusion},
    'no-match-user'      => q{Aucune entrée trouvée à cause options d'exclusion/inclusion},
    'no-parse-psql'      => q{N'a pas pu analyser la sortie de psql !},
    'no-time-hires'      => q{N'a pas trouvé le module Time::HiRes, nécessaire quand « showtime » est activé},
    'opt-output-invalid' => q{Sortie invalide : doit être 'nagios' ou 'mrtg' ou 'simple' ou 'cacti'},
    'opt-psql-badpath'   => q{Argument invalide pour psql : doit être le chemin complet vers un fichier nommé psql},
    'opt-psql-noexec'    => q{ Le fichier « $1 » ne paraît pas exécutable},
    'opt-psql-noexist'   => q{Ne peut pas trouver l'exécutable psql indiqué : $1},
    'opt-psql-nofind'    => q{N'a pas pu trouver un psql exécutable},
    'opt-psql-nover'     => q{N'a pas pu déterminer la version de psql},
    'opt-psql-restrict'  => q{Ne peut pas utiliser l'option --PGBINDIR ou --PSQL si NO_PSQL_OPTION est activé},
'pgagent-jobs-ok'    => q{No failed jobs},
    'pgbouncer-pool'     => q{Pool=$1 $2=$3},
    'pgb-backends-mrtg'  => q{base=$1 connexions max=$2},
    'pgb-backends-msg'   => q{$1 connexions sur $2 ($3%)},
    'pgb-backends-none'  => q{Aucune connection},
    'pgb-backends-users' => q{Le nombre d'utilisateurs, $1, doit être un nombre ou un pourcentage},
    'PID'                => q{PID},
    'port'               => q{port},
    'preptxn-none'       => q{Aucune transaction préparée trouvée},
    'psa-disabled'       => q{Pas de requ??te - est-ce que stats_command_string ou track_activities sont d??sactiv??s ?},
    'psa-noexact'        => q{Erreur inconnue},
    'psa-nosuper'        => q{Aucune correspondance - merci de m'ex??cuter en tant que superutilisateur},
    'qtime-count-msg'    => q{Requêtes totales : $1},
    'qtime-count-none'   => q{pas plus que $1 requêtes},
    'qtime-for-msg'      => q{$1 requêtes plus longues que $2s, requête la plus longue : $3s$4 $5},
    'qtime-msg'          => q{requête la plus longue : $1s$2 $3},
    'qtime-none'         => q{aucune requête},
    'query'              => q{requête},
    'queries'            => q{requêtes},
    'query-time'         => q{durée de la requête},
    'range-badcs'        => q{Option « $1 » invalide : doit être une somme de contrôle},
    'range-badlock'      => q{Option « $1 » invalide : doit être un nombre de verrou ou « type1=#:type2=# »},
    'range-badpercent'   => q{Option « $1 » invalide : doit être un pourcentage},
    'range-badpercsize'  => q{Option « $1 » invalide : doit être une taille ou un pourcentage},
    'range-badsize'      => q{Taille invalide pour l'option « $1 »},
    'range-badtype'      => q{validate_range appelé avec un type inconnu « $1 »},
    'range-badversion'   => q{Chaîne invalide pour l'option « $1 » : $2},
    'range-cactionly'    => q{Cette action est pour cacti seulement et ne prend pas les arguments warning et critical},
    'range-int'          => q{Argument invalide pour l'option « $1 » : doit être un entier},
    'range-int-pos'      => q{Argument invalide pour l'option « $1 » : doit être un entier positif},
    'range-neg-percent'  => q{Ne peut pas indiquer un pourcentage négatif !},
    'range-none'         => q{Les options warning et critical ne sont pas nécessaires},
    'range-noopt-both'   => q{Doit fournir les options warning et critical},
    'range-noopt-one'    => q{Doit fournir une option warning ou critical},
    'range-noopt-only'   => q{Peut seulement fournir une option warning ou critical},
    'range-noopt-orboth' => q{Doit fournir une option warning, une option critical ou les deux},
    'range-noopt-size'   => q{Doit fournir une taille warning et/ou critical},
    'range-nosize'       => q{Doit fournir une taille warning et/ou critical},
    'range-notime'       => q{Doit fournir une heure warning et/ou critical},
    'range-seconds'      => q{Argument invalide pour l'option « $1 » : doit être un nombre de secondes},
    'range-version'      => q{doit être dans le format X.Y ou X.Y.Z, où X est le numéro de version majeure, },
    'range-warnbig'      => q{L'option warning ne peut pas être plus grand que l'option critical},
    'range-warnbigsize'  => q{L'option warning ($1 octets) ne peut pas être plus grand que l'option critical ($2 octets)},
    'range-warnbigtime'  => q{L'option warning ($1 s) ne peut pas être plus grand que l'option critical ($2 s)},
    'range-warnsmall'    => q{L'option warningne peut pas être plus petit que l'option critical},
    'range-nointfortime' => q{Argument invalide pour l'option '$1' : doit être un entier, une heure ou un entier horaire},
    'relsize-msg-ind'    => q{le plus gros index est « $1 » : $2},
    'relsize-msg-reli'   => q{la plus grosse relation est l'index « $1 » : $2},
    'relsize-msg-relt'   => q{la plus grosse relation est la table « $1 » : $2},
    'relsize-msg-tab'    => q{la plus grosse table est « $1 » : $2},
    'rep-badarg'         => q{Argument repinfo invalide : 6 valeurs séparées par des virgules attendues},
    'rep-duh'            => q{Aucun sens à tester la réplication avec les mêmes valeurs},
    'rep-fail'           => q{Ligne non répliquée sur l'esclave $1},
    'rep-noarg'          => q{A besoin d'un argument repinfo},
    'rep-norow'          => q{Ligne source de la réplication introuvable : $1},
    'rep-noslaves'       => q{Aucun esclave trouvé},
    'rep-notsame'        => q{Ne peut pas tester la réplication : les valeurs ne sont pas identiques},
    'rep-ok'             => q{La ligne a été répliquée},
    'rep-sourcefail'     => q{Échec de la mise à jour de la source},
    'rep-timeout'        => q{La ligne n'a pas été répliquée. Délai dépassé : $1},
    'rep-unknown'        => q{Échec du test de la réplication},
    'rep-wrongvals'      => q{Ne peut pas tester la réplication : les valeurs ne sont pas les bonnes (ni '$1' ni '$2' ni '$3')},
    'runcommand-err'     => q{Erreur inconnue de la fonction « run_command »},
    'runcommand-nodb'    => q{Aucune base de données cible trouvée},
    'runcommand-nodupe'  => q{N'a pas pu dupliqué STDERR},
    'runcommand-noerr'   => q{N'a pas pu ouvrir STDERR},
    'runcommand-nosys'   => q{Échec de l'appel système avec un $1},
    'runcommand-pgpass'  => q{Création du fichier pgpass temporaire $1},
    'runcommand-timeout' => q{Délai épuisée pour la commande ! Essayez d'augmenter --timeout à une valeur plus importante que $1},
    'runtime-badmrtg'    => q{queryname invalide ?},
    'runtime-badname'    => q{Option invalide pour queryname option : doit être le nom d'une vue},
    'runtime-msg'        => q{durée d'exécution de la requête : $1 secondes},
    'schema'             => q{Schéma},
    'ss-createfile'      => q{Création du fichier $1},
    'ss-different'       => q{"$1" est différent:},
    'ss-existson'        => q{Existe sur :},
    'ss-failed'          => q{Les bases de données sont différentes. Éléments différents : $1},
    'ss-matched'         => q{Les bases de données ont les mêmes éléments},
    'ss-missingon'       => q{Manque sur :},
    'ss-noexist'         => q{$1 "$2" n'existe pas sur toutes les bases de données :},
    'ss-notset'          => q{"$1" n'est pas configuré sur toutes les bases de données :},
    'ss-suffix'          => q{Erreur : ne peut pas utiliser le suffixe sauf à rechercher des schémas basés sur l'horloge},
    'size'               => q{taille},
    'slony-noschema'     => q{N'a pas pu déterminer le schéma de Slony},
    'slony-nonumber'     => q{L'appel à sl_status n'a pas renvoyé un numéro},
    'slony-lagtime'      => q{Durée de lag de Slony : $1},
    'seq-die'            => q{N'a pas pu récupérer d'informations sur la séquence $1},
    'seq-msg'            => q{$1=$2% (appels restant=$3)},
    'seq-none'           => q{Aucune sequences trouvée},
    'symlink-create'     => q{Création de « $1 »},
    'symlink-done'       => q{Création impossible de « $1 »: $2 est déjà lié à "$3"},
    'symlink-exists'     => q{Création impossible de « $1 »: le fichier $2 existe déjà},
    'symlink-fail1'      => q{Échec de la suppression de « $1 » : $2},
    'symlink-fail2'      => q{N'a pas pu supprimer le lien symbolique $1 vers $2 : $3},
    'symlink-name'       => q{Cette commande ne fonctionnera pas sauf si le programme contient le mot « postgres »},
    'symlink-unlink'     => q{Supression de « $1 » :$2 },
    'table'              => q{Table},
    'testmode-end'       => q{FIN DU MODE DE TEST},
    'testmode-fail'      => q{Échec de la connexion : $1 $2},
    'testmode-norun'     => q{N'a pas pu exécuter « $1 » sur $2 : la version doit être supérieure ou égale à $3, mais est $4},
    'testmode-noset'     => q{N'a pas pu exécuter « $1 » sur $2 : $3 n'est pas activé},
    'testmode-nover'     => q{N'a pas pu trouver la version de $1},
    'testmode-ok'        => q{Connexion OK : $1},
    'testmode-start'     => q{DÉBUT DU MODE DE TEST},
    'time-day'           => q{jour},
    'time-days'          => q{jours},
    'time-hour'          => q{heure},
    'time-hours'         => q{heures},
    'time-minute'        => q{minute},
    'time-minutes'       => q{minutes},
    'time-month'         => q{mois},
    'time-months'        => q{mois},
    'time-second'        => q{seconde},
    'time-seconds'       => q{secondes},
    'time-week'          => q{semaine},
    'time-weeks'         => q{semaines},
    'time-year'          => q{année},
    'time-years'         => q{années},
    'timesync-diff'      => q{diff},
    'timesync-msg'       => q{timediff=$1 Base de données=$2 Local=$3},
    'transactions'       => q{transactions},
    'trigger-msg'        => q{Triggers désactivés : $1},
    'txn-time'           => q{durée de la transaction},
    'txnidle-count-msg'  => q{Transactions en attente totales : $1},
    'txnidle-count-none' => q{pas plus de $1 transaction en attente},
    'txnidle-for-msg'    => q{$1 transactions en attente plus longues que $2s, transaction la plus longue : $3s$4 $5},
    'txnidle-msg'        => q{transaction en attente la plus longue : $1s$2 $3},
    'txnidle-none'       => q{Aucun processus en attente dans une transaction},
    'txntime-count-msg'  => q{Transactions totales : $1},
    'txntime-count-none' => q{pas plus que $1 transactions},
    'txntime-for-msg'    => q{$1 transactions plus longues que $2s, transaction la plus longue : $3s$4 $5},
    'txntime-msg'        => q{Transaction la plus longue : $1s$2 $3},
    'txntime-none'       => q{Aucune transaction},
    'txnwrap-cbig'       => q{La valeur critique doit être inférieure à 2 milliards},
    'txnwrap-wbig'       => q{La valeur d'avertissement doit être inférieure à 2 milliards},
    'unknown-error'      => q{erreur inconnue},
    'usage'              => qq{\nUsage: \$1 <options>\n Essayez « \$1 --help » pour liste complète des options\n\n},
    'username'           => q{nom utilisateur},
    'user'               => q{Utilisateur},
    'vac-nomatch-a'      => q{Aucune des tables correspondantes n'a eu d'opération ANALYZE},
    'vac-nomatch-v'      => q{Aucune des tables correspondantes n'a eu d'opération VACUUM},
    'version'            => q{version $1},
    'version-badmrtg'    => q{Argument invalide pour la version de mrtg},
    'version-fail'       => q{version $1, alors que la version attendue est $2},
    'version-ok'         => q{version $1},
    'wal-numfound'       => q{Fichiers WAL trouvés : $1},
    'wal-numfound2'      => q{Fichiers WAL "$2" trouvés : $1},
},
'af' => {
},
'cs' => {
    'checkpoint-po' => q{�as posledn�ho kontroln�ho bodu:},
},
'de' => {
    'backends-po'   => q{tut mir leid, schon zu viele Verbindungen},
    'checkpoint-po' => q{Zeit des letzten Checkpoints:},
},
'es' => {
    'backends-po'   => q{lo siento, ya tenemos demasiados clientes},
    'checkpoint-po' => q{Instante de �ltimo checkpoint:},
},
'fa' => {
    'checkpoint-po' => q{زمان آخرین وارسی:},
},
'hr' => {
    'backends-po' => q{nažalost, već je otvoreno previše klijentskih veza},
},
'hu' => {
    'checkpoint-po' => q{A legut�bbi ellen�rz�pont ideje:},
},
'it' => {
    'checkpoint-po' => q{Orario ultimo checkpoint:},
},
'ja' => {
    'backends-po'   => q{現在クライアント数が多すぎます},
    'checkpoint-po' => q{最終チェックポイント時刻:},
},
'ko' => {
    'backends-po'   => q{최대 동시 접속자 수를 초과했습니다.},
    'checkpoint-po' => q{������ üũ����Ʈ �ð�:},
},
'nb' => {
    'backends-po'   => q{beklager, for mange klienter},
    'checkpoint-po' => q{Tidspunkt for nyeste kontrollpunkt:},
},
'nl' => {
},
'pl' => {
    'checkpoint-po' => q{Czas najnowszego punktu kontrolnego:},
},
'pt_BR' => {
    'backends-po'   => q{desculpe, muitos clientes conectados},
    'checkpoint-po' => q{Hora do último ponto de controle:},
},
'ro' => {
    'checkpoint-po' => q{Timpul ultimului punct de control:},
},
'ru' => {
    'backends-po'   => q{��������, ��� ������� ����� ��������},
    'checkpoint-po' => q{����� ��������� checkpoint:},
},
'sk' => {
    'backends-po'   => q{je mi ��to, je u� pr�li� ve�a klientov},
    'checkpoint-po' => q{Čas posledného kontrolného bodu:},
},
'sl' => {
    'backends-po'   => q{povezanih je �e preve� odjemalcev},
    'checkpoint-po' => q{�as zadnje kontrolne to�ke ............},
},
'sv' => {
    'backends-po'   => q{ledsen, f�r m�nga klienter},
    'checkpoint-po' => q{Tidpunkt f�r senaste kontrollpunkt:},
},
'ta' => {
    'checkpoint-po' => q{நவீன சோதனை மையத்தின் நேரம்:},
},
'tr' => {
    'backends-po'   => q{üzgünüm, istemci sayısı çok fazla},
    'checkpoint-po' => q{En son checkpoint'in zamanı:},
},
'zh_CN' => {
    'backends-po'   => q{�Բ���, �Ѿ���̫���Ŀͻ�},
    'checkpoint-po' => q{���¼�������ʱ��:},
},
'zh_TW' => {
    'backends-po'   => q{對不起，用戶端過多},
    'checkpoint-po' => q{最新的檢查點時間:},
},
);
## use critic

our $lang = $ENV{LC_ALL} || $ENV{LC_MESSAGES} || $ENV{LANG} || 'en';
$lang = substr($lang,0,2);

## Messages are stored in these until the final output via finishup()
our (%ok, %warning, %critical, %unknown);

our $ME = basename($0);
our $ME2 = 'check_postgres.pl';
our $USAGE = msg('usage', $ME);

## This gets turned on for meta-commands which don't hit a Postgres database
our $nohost = 0;

## Global error string, mostly used for MRTG error handling
our $ERROR = '';

$opt{test} = 0;
$opt{timeout} = 30;

## Look for any rc files to control additional parameters
## Command line options always overwrite these
## Format of these files is simply name=val

## This option must come before the GetOptions call
for my $arg (@ARGV) {
    if ($arg eq '--no-check_postgresrc') {
        $opt{'no-check_postgresrc'} = 1;
        last;
    }
}

## Used by same_schema in the find_catalog_info sub
my %catalog_info = (

    user => {
        SQL        => q{
SELECT *, usename AS name, quote_ident(usename) AS safeusename
FROM pg_user},
        deletecols => [ qw{ passwd } ],
    },

    schema => {
        SQL       => q{
SELECT n.oid, quote_ident(nspname) AS name, quote_ident(usename) AS owner, nspacl
FROM pg_namespace n
JOIN pg_user u ON (u.usesysid = n.nspowner)},
        deletecols => [ ],
        exclude    => 'temp_schemas',
    },
    language => {
        SQL       => q{
SELECT l.*, lanname AS name, quote_ident(usename) AS owner
FROM pg_language l
JOIN pg_user u ON (u.usesysid = l.lanowner)},
        SQL2       => q{
SELECT l.*, lanname AS name
FROM pg_language l
    },
    },
    type => {
        SQL       => q{
SELECT t.oid AS oid, t.*, quote_ident(usename) AS owner, quote_ident(nspname) AS schema,
  nspname||'.'||typname AS name
FROM pg_type t
JOIN pg_user u ON (u.usesysid = t.typowner)
JOIN pg_namespace n ON (n.oid = t.typnamespace)
WHERE t.typtype NOT IN ('b','c')},
        exclude    => 'system',
    },
    sequence => {
        SQL       => q{
SELECT c.*, nspname||'.'||relname AS name, quote_ident(usename) AS owner,
  (quote_ident(nspname)||'.'||quote_ident(relname)) AS safename,
quote_ident(nspname) AS schema
FROM pg_class c
JOIN pg_user u ON (u.usesysid = c.relowner)
JOIN pg_namespace n ON (n.oid = c.relnamespace)
WHERE c.relkind = 'S'},
        innerSQL   => 'SELECT * FROM ROWSAFENAME',
    },
    view => {
        SQL       => q{
SELECT c.*, nspname||'.'||relname AS name, quote_ident(usename) AS owner,
  quote_ident(relname) AS safename, quote_ident(nspname) AS schema,
  TRIM(pg_get_viewdef(c.oid, TRUE)) AS viewdef, spcname AS tablespace
FROM pg_class c
JOIN pg_user u ON (u.usesysid = c.relowner)
JOIN pg_namespace n ON (n.oid = c.relnamespace)
LEFT JOIN pg_tablespace s ON (s.oid = c.reltablespace)
WHERE c.relkind = 'v'},
        exclude    => 'system',
    },
    table => {
        SQL       => q{
SELECT c.*, nspname||'.'||relname AS name, quote_ident(usename) AS owner,
  quote_ident(relname) AS safename, quote_ident(nspname) AS schema,
  spcname AS tablespace
FROM pg_class c
JOIN pg_user u ON (u.usesysid = c.relowner)
JOIN pg_namespace n ON (n.oid = c.relnamespace)
LEFT JOIN pg_tablespace s ON (s.oid = c.reltablespace)
WHERE c.relkind = 'r'},
        exclude    => 'system',
    },
    index => {
        SQL       => q{
SELECT c.*, i.*, nspname||'.'||relname AS name, quote_ident(usename) AS owner,
  quote_ident(relname) AS safename, quote_ident(nspname) AS schema,
  spcname AS tablespace, amname,
  pg_get_indexdef(c.oid) AS indexdef
FROM pg_class c
JOIN pg_user u ON (u.usesysid = c.relowner)
JOIN pg_namespace n ON (n.oid = c.relnamespace)
JOIN pg_index i ON (c.oid = i.indexrelid)
LEFT JOIN pg_tablespace s ON (s.oid = c.reltablespace)
LEFT JOIN pg_am a ON (a.oid = c.relam)
WHERE c.relkind = 'i'},
        exclude    => 'system',
    },
    operator => {
        SQL       => q{
SELECT o.*, o.oid, nspname||'.'||o.oprname AS name, quote_ident(o.oprname) AS safename,
  usename AS owner, nspname AS schema,
  t1.typname AS resultname,
  t2.typname AS leftname, t3.typname AS rightname
FROM pg_operator o
JOIN pg_user u ON (u.usesysid = o.oprowner)
JOIN pg_namespace n ON (n.oid = o.oprnamespace)
JOIN pg_proc p1 ON (p1.oid = o.oprcode)
JOIN pg_type t1 ON (t1.oid = o.oprresult)
LEFT JOIN pg_type t2 ON (t2.oid = o.oprleft)
LEFT JOIN pg_type t3 ON (t3.oid = o.oprright)},
        exclude    => 'system',
    },
    trigger => {
        SQL       => q{
SELECT t.*, n1.nspname||'.'||t.tgname AS name, quote_ident(t.tgname) AS safename, quote_ident(usename) AS owner,
  n1.nspname AS tschema, c1.relname AS tname,
  n2.nspname AS cschema, c2.relname AS cname,
  n3.nspname AS procschema, p.proname AS procname
FROM pg_trigger t
JOIN pg_class c1 ON (c1.oid = t.tgrelid)
JOIN pg_user u ON (u.usesysid = c1.relowner)
JOIN pg_namespace n1 ON (n1.oid = c1.relnamespace)
JOIN pg_proc p ON (p.oid = t.tgfoid)
JOIN pg_namespace n3 ON (n3.oid = p.pronamespace)
LEFT JOIN pg_class c2 ON (c2.oid = t.tgconstrrelid)
LEFT JOIN pg_namespace n2 ON (n2.oid = c2.relnamespace)
WHERE t.tgconstrrelid = 0 AND tgname !~ '^pg_'},
    },
    function => {
        SQL       => q{
SELECT p.*, p.oid, nspname||'.'||p.proname AS name, quote_ident(p.proname) AS safename,
  md5(prosrc) AS source_checksum,
  usename AS owner, nspname AS schema
FROM pg_proc p
JOIN pg_user u ON (u.usesysid = p.proowner)
JOIN pg_namespace n ON (n.oid = p.pronamespace)},
        exclude    => 'system',
    },
    constraint => {
        SQL       => q{
SELECT c.*, c.oid, n.nspname||'.'||c.conname AS name, quote_ident(c.conname) AS safename,
 n.nspname AS schema, relname AS tname
FROM pg_constraint c
JOIN pg_namespace n ON (n.oid = c.connamespace)
JOIN pg_class r ON (r.oid = c.conrelid)
JOIN pg_namespace n2 ON (n2.oid = r.relnamespace)},
        exclude    => 'system',
    },
    column => {
        SQL       => q{
SELECT a.*, n.nspname||'.'||c.relname||'.'||attname AS name, quote_ident(a.attname) AS safename,
  n.nspname||'.'||c.relname AS tname,
  typname, quote_ident(nspname) AS schema,
  pg_get_expr(d.adbin, a.attrelid, true) AS default
FROM pg_attribute a
JOIN pg_type t ON (t.oid = a.atttypid)
JOIN pg_class c ON (c.oid = a.attrelid AND c.relkind = 'r')
JOIN pg_namespace n ON (n.oid = c.relnamespace)
LEFT JOIN pg_attrdef d ON (d.adrelid = a.attrelid AND d.adnum = a.attnum)
WHERE attnum >= 1
AND NOT attisdropped},
        postSQL    => q{ORDER BY n.nspname, c.relname, a.attnum},
        exclude    => 'system',
    },
);

my $rcfile;
if (! $opt{'no-check_postgresrc'}) {
    if (-e '.check_postgresrc') {
        $rcfile = '.check_postgresrc';
    }
    elsif (exists $ENV{HOME} and -e "$ENV{HOME}/.check_postgresrc") {
        $rcfile = "$ENV{HOME}/.check_postgresrc";
    }
    elsif (-e '/etc/check_postgresrc') {
        $rcfile = '/etc/check_postgresrc';
    }
    elsif (-e '/usr/local/etc/check_postgresrc') {
        $rcfile = '/usr/local/etc/check_postgresrc';
    }
}
## We need a temporary hash so that multi-value options can be overridden on the command line
my %tempopt;
if (defined $rcfile) {
    open my $rc, '<', $rcfile or die qq{Could not open "$rcfile": $!\n};
    RCLINE:
    while (<$rc>) {
        next if /^\s*#/;
        next unless /^\s*(\w+)\s*=\s*(.+?)\s*$/o;
        my ($name,$value) = ($1,$2); ## no critic (ProhibitCaptureWithoutTest)
        ## Map alternate option spellings to preferred names
        if ($name eq 'dbport' or $name eq 'p' or $name eq 'dbport1' or $name eq 'p1' or $name eq 'port1') {
            $name = 'port';
        }
        elsif ($name eq 'dbhost' or $name eq 'H' or $name eq 'dbhost1' or $name eq 'H1' or $name eq 'host1') {
            $name = 'host';
        }
        elsif ($name eq 'db' or $name eq 'db1' or $name eq 'dbname1') {
            $name = 'dbname';
        }
        elsif ($name eq 'u' or $name eq 'u1' or $name eq 'dbuser1') {
            $name = 'dbuser';
        }
        ## Now for all the additional non-1 databases
        elsif ($name =~ /^dbport(\d+)$/o or $name eq /^p(\d+)$/o) {
            $name = "port$1";
        }
        elsif ($name =~ /^dbhost(\d+)$/o or $name eq /^H(\d+)$/o) {
            $name = "host$1";
        }
        elsif ($name =~ /^db(\d)$/o) {
            $name = "dbname$1";
        }
        elsif ($name =~ /^u(\d+)$/o) {
            $name = "dbuser$1";
        }

        ## These options are multiples ('@s')
        for my $arr (qw/include exclude includeuser excludeuser host port
                        dbuser dbname dbpass dbservice schema/) {
            next if $name ne $arr and $name ne "${arr}2";
            push @{$tempopt{$name}} => $value;
            ## Don't set below as a normal value
            next RCLINE;
        }
        $opt{$name} = $value;
    }
    close $rc or die;
}

die $USAGE if ! @ARGV;

GetOptions(
    \%opt,
    'version|V',
    'verbose|v+',
    'vv',
    'help|h',
    'quiet|q',
    'man',
    'output=s',
    'simple',
    'showperf=i',
    'perflimit=i',
    'showtime=i',
    'timeout|t=i',
    'test',
    'symlinks',
    'debugoutput=s',
    'no-check_postgresrc',
    'assume-standby-mode',
    'assume-prod',

    'action=s',
    'warning=s',
    'critical=s',
    'include=s@',
    'exclude=s@',
    'includeuser=s@',
    'excludeuser=s@',

    'host|dbhost|H|dbhost1|H1=s@',
    'port|dbport|p|port1|dbport1|p1=s@',
    'dbname|db|dbname1|db1=s@',
    'dbuser|u|dbuser1|u1=s@',
    'dbpass|dbpass1=s@',
    'dbservice|dbservice1=s@',

    'PGBINDIR=s',
    'PSQL=s',

    'tempdir=s',
    'get_method=s',
    'language=s',
    'mrtg=s',      ## used by MRTG checks only
    'logfile=s',   ## used by check_logfile only
    'queryname=s', ## used by query_runtime only
    'query=s',     ## used by custom_query only
    'valtype=s',   ## used by custom_query only
    'reverse',     ## used by custom_query only
    'repinfo=s',   ## used by replicate_row only
    'noidle',      ## used by backends only
    'datadir=s',   ## used by checkpoint only
    'schema=s@',   ## used by slony_status only
    'filter=s@',   ## used by same_schema only
    'suffix=s',    ## used by same_schema only
    'replace',     ## used by same_schema only
);

die $USAGE if ! keys %opt and ! @ARGV;

## Process the args that are not so easy for Getopt::Long
my @badargs;

while (my $arg = pop @ARGV) {

    ## These must be of the form x=y
    if ($arg =~ /^\-?\-?(\w+)\s*=\s*(.+)/o) {
        my ($name,$value) = (lc $1, $2);
        if ($name =~ /^(?:db)?port(\d+)$/o or $name =~ /^p(\d+)$/o) {
            push @{ $opt{port} } => $value;
        }
        elsif ($name =~ /^(?:db)?host(\d+)$/o or $name =~ /^H(\d+)$/o) {
            push @{ $opt{host} } => $value;
        }
        elsif ($name =~ /^db(?:name)?(\d+)$/o) {
            push @{ $opt{dbname} } => $value;
        }
        elsif ($name =~ /^dbuser(\d+)$/o or $name =~ /^u(\d+)/o) {
            push @{ $opt{dbuser} } => $value;
        }
        elsif ($name =~ /^dbpass(\d+)$/o) {
            push @{ $opt{dbpass} } => $value;
        }
        elsif ($name =~ /^dbservice(\d+)$/o) {
            push @{ $opt{dbservice} } => $value;
        }
        else {
            push @badargs => $arg;
        }
        next;
    }
    push @badargs => $arg;
}

if (@badargs) {
    warn "Invalid arguments:\n";
    for (@badargs) {
        warn "  $_\n";
    }
    die $USAGE;
}

if ( $opt{man} ) {
    require Pod::Usage;
    Pod::Usage::pod2usage({-verbose => 2});
    exit;
}

## Put multi-val options from check_postgresrc in place, only if no command-line args!
for my $mv (keys %tempopt) {
    $opt{$mv} ||= delete $tempopt{$mv};
}

our $VERBOSE = $opt{verbose} || 0;
$VERBOSE = 5 if $opt{vv};

our $OUTPUT = lc($opt{output} || '');

## Allow the optimization of the get_methods list by an argument
if ($opt{get_method}) {
    my $found = 0;
    for my $meth (@get_methods) {
        if ($meth =~ /^$opt{get_method}/io) {
            @get_methods = ($meth);
            $found = 1;
            last;
        }
    }
    if (!$found) {
        print "Unknown value for get_method: $opt{get_method}\n";
        print "Valid choices are:\n";
        print (join "\n" => map { s/(\w+).*/$1/; $_ } @get_methods);
        print "\n";
        exit;
    }
}

## Allow the language to be changed by an explicit option
if ($opt{language}) {
    $lang = substr($opt{language},0,2);
}

## Output the actual string returned by psql in the normal output
## Argument is 'a' for all, 'w' for warning, 'c' for critical, 'u' for unknown
## Can be grouped together
our $DEBUGOUTPUT = $opt{debugoutput} || '';
our $DEBUG_INFO = '?';

## If not explicitly given an output, check the current directory,
## then fall back to the default.

if (!$OUTPUT) {
    my $dir = getcwd;
    if ($dir =~ /(nagios|mrtg|simple|cacti)/io) {
        $OUTPUT = lc $1;
    }
    elsif ($opt{simple}) {
        $OUTPUT = 'simple';
    }
    else {
        $OUTPUT = $DEFAULT_OUTPUT;
    }
}


## Extract transforms from the output
$opt{transform} = '';
if ($OUTPUT =~ /\b(kb|mb|gb|tb|eb)\b/) {
    $opt{transform} = uc $1;
}
if ($OUTPUT =~ /(nagios|mrtg|simple|cacti)/io) {
    $OUTPUT = lc $1;
}
## Check for a valid output setting
if ($OUTPUT ne 'nagios' and $OUTPUT ne 'mrtg' and $OUTPUT ne 'simple' and $OUTPUT ne 'cacti') {
    die msgn('opt-output-invalid');
}

our $MRTG = ($OUTPUT eq 'mrtg' or $OUTPUT eq 'simple') ? 1 : 0;
our (%stats, %statsmsg);
our $SIMPLE = $OUTPUT eq 'simple' ? 1 : 0;

## See if we need to invoke something based on our name
our $action = $opt{action} || '';
if ($ME =~ /check_postgres_(\w+)/ and ! defined $opt{action}) {
    $action = $1;
}

$VERBOSE >= 3 and warn Dumper \%opt;

if ($opt{version}) {
    print qq{$ME2 version $VERSION\n};
    exit 0;
}

## Quick hash to put normal action information in one place:
our $action_info = {
 # Name                 # clusterwide? # helpstring
 archive_ready       => [1, 'Check the number of WAL files ready in the pg_xlog/archive_status'],
 autovac_freeze      => [1, 'Checks how close databases are to autovacuum_freeze_max_age.'],
 backends            => [1, 'Number of connections, compared to max_connections.'],
 bloat               => [0, 'Check for table and index bloat.'],
 checkpoint          => [1, 'Checks how long since the last checkpoint'],
 cluster_id          => [1, 'Checks the Database System Identifier'],
 commitratio         => [0, 'Report if the commit ratio of a database is too low.'],
 connection          => [0, 'Simple connection check.'],
 custom_query        => [0, 'Run a custom query.'],
 database_size       => [0, 'Report if a database is too big.'],
 dbstats             => [1, 'Returns stats from pg_stat_database: Cacti output only'],
 disabled_triggers   => [0, 'Check if any triggers are disabled'],
 disk_space          => [1, 'Checks space of local disks Postgres is using.'],
 fsm_pages           => [1, 'Checks percentage of pages used in free space map.'],
 fsm_relations       => [1, 'Checks percentage of relations used in free space map.'],
 hitratio            => [0, 'Report if the hit ratio of a database is too low.'],
 hot_standby_delay   => [1, 'Check the replication delay in hot standby setup'],
 index_size          => [0, 'Checks the size of indexes only.'],
 table_size          => [0, 'Checks the size of tables only.'],
 relation_size       => [0, 'Checks the size of tables and indexes.'],
 last_analyze        => [0, 'Check the maximum time in seconds since any one table has been analyzed.'],
 last_vacuum         => [0, 'Check the maximum time in seconds since any one table has been vacuumed.'],
 last_autoanalyze    => [0, 'Check the maximum time in seconds since any one table has been autoanalyzed.'],
 last_autovacuum     => [0, 'Check the maximum time in seconds since any one table has been autovacuumed.'],
 listener            => [0, 'Checks for specific listeners.'],
 locks               => [0, 'Checks the number of locks.'],
 logfile             => [1, 'Checks that the logfile is being written to correctly.'],
 new_version_bc      => [0, 'Checks if a newer version of Bucardo is available.'],
 new_version_box     => [0, 'Checks if a newer version of boxinfo is available.'],
 new_version_cp      => [0, 'Checks if a newer version of check_postgres.pl is available.'],
 new_version_pg      => [0, 'Checks if a newer version of Postgres is available.'],
 new_version_tnm     => [0, 'Checks if a newer version of tail_n_mail is available.'],
 pgb_pool_cl_active  => [1, 'Check the number of active clients in each pgbouncer pool.'],
 pgb_pool_cl_waiting => [1, 'Check the number of waiting clients in each pgbouncer pool.'],
 pgb_pool_sv_active  => [1, 'Check the number of active server connections in each pgbouncer pool.'],
 pgb_pool_sv_idle    => [1, 'Check the number of idle server connections in each pgbouncer pool.'],
 pgb_pool_sv_used    => [1, 'Check the number of used server connections in each pgbouncer pool.'],
 pgb_pool_sv_tested  => [1, 'Check the number of tested server connections in each pgbouncer pool.'],
 pgb_pool_sv_login   => [1, 'Check the number of login server connections in each pgbouncer pool.'],
 pgb_pool_maxwait    => [1, 'Check the current maximum wait time for client connections in pgbouncer pools.'],
 pgbouncer_backends  => [0, 'Check how many clients are connected to pgbouncer compared to max_client_conn.'],
 pgbouncer_checksum  => [0, 'Check that no pgbouncer settings have changed since the last check.'],
 pgagent_jobs        => [0, 'Check for no failed pgAgent jobs within a specified period of time.'],
 prepared_txns       => [1, 'Checks number and age of prepared transactions.'],
 query_runtime       => [0, 'Check how long a specific query takes to run.'],
 query_time          => [1, 'Checks the maximum running time of current queries.'],
 replicate_row       => [0, 'Verify a simple update gets replicated to another server.'],
 same_schema         => [0, 'Verify that two databases have the exact same tables, columns, etc.'],
 sequence            => [0, 'Checks remaining calls left in sequences.'],
 settings_checksum   => [0, 'Check that no settings have changed since the last check.'],
 slony_status        => [1, 'Ensure Slony is up to date via sl_status.'],
 timesync            => [0, 'Compare database time to local system time.'],
 txn_idle            => [1, 'Checks the maximum "idle in transaction" time.'],
 txn_time            => [1, 'Checks the maximum open transaction time.'],
 txn_wraparound      => [1, 'See how close databases are getting to transaction ID wraparound.'],
 version             => [1, 'Check for proper Postgres version.'],
 wal_files           => [1, 'Check the number of WAL files in the pg_xlog directory'],
};

## XXX Need to i18n the above
our $action_usage = '';
our $longname = 1;
for (keys %$action_info) {
    $longname = length($_) if length($_) > $longname;
}
for (sort keys %$action_info) {
    $action_usage .= sprintf " %-*s - %s\n", 2+$longname, $_, $action_info->{$_}[1];
}


if ($opt{help}) {
    print qq{Usage: $ME2 <options>
Run various tests against one or more Postgres databases.
Returns with an exit code of 0 (success), 1 (warning), 2 (critical), or 3 (unknown)
This is version $VERSION.

Common connection options:
 -H,  --host=NAME       hostname(s) to connect to; defaults to none (Unix socket)
 -p,  --port=NUM        port(s) to connect to; defaults to $opt{defaultport}.
 -db, --dbname=NAME     database name(s) to connect to; defaults to 'postgres' or 'template1'
 -u   --dbuser=NAME     database user(s) to connect as; defaults to '$opt{defaultuser}'
      --dbpass=PASS     database password(s); use a .pgpass file instead when possible
      --dbservice=NAME  service name to use inside of pg_service.conf

Connection options can be grouped: --host=a,b --host=c --port=1234 --port=3344
would connect to a-1234, b-1234, and c-3344

Limit options:
  -w value, --warning=value   the warning threshold, range depends on the action
  -c value, --critical=value  the critical threshold, range depends on the action
  --include=name(s) items to specifically include (e.g. tables), depends on the action
  --exclude=name(s) items to specifically exclude (e.g. tables), depends on the action
  --includeuser=include objects owned by certain users
  --excludeuser=exclude objects owned by certain users

Other options:
  --assume-standby-mode assume that server in continious WAL recovery mode
  --assume-prod         assume that server in production mode
  --PGBINDIR=PATH       path of the postgresql binaries; avoid using if possible
  --PSQL=FILE           (deprecated) location of the psql executable; avoid using if possible
  -v, --verbose         verbosity level; can be used more than once to increase the level
  -h, --help            display this help information
  --man                 display the full manual
  -t X, --timeout=X     how long in seconds before we timeout. Defaults to 30 seconds.
  --symlinks            create named symlinks to the main program for each action

Actions:
Which test is determined by the --action option, or by the name of the program
$action_usage

For a complete list of options and full documentation, view the manual.

    $ME --man

Or visit: http://bucardo.org/check_postgres/


};
    exit 0;
}

build_symlinks() if $opt{symlinks};

$action =~ /\w/ or die $USAGE;

## Be nice and figure out what they meant
$action =~ s/\-/_/g;
$action = lc $action;

## Build symlinked copies of this file
build_symlinks() if $action =~ /build_symlinks/; ## Does not return, may be 'build_symlinks_force'

## Die if Time::HiRes is needed but not found
if ($opt{showtime}) {
    eval {
        require Time::HiRes;
        import Time::HiRes qw/gettimeofday tv_interval sleep/;
    };
    if ($@) {
        die msg('no-time-hires');
    }
}

## We don't (usually) want to die, but want a graceful Nagios-like exit instead
sub ndie {
    eval { File::Temp::cleanup(); };
    my $msg = shift;
    chomp $msg;
    ## If this message already starts with an ERROR, filter that out for prettiness
    $msg =~ s/^\s*ERROR:\s*/ /;
    ## Trim whitespace
    $msg =~ s/^\s*(.+)\s*$/$1/;
    print "ERROR: $msg\n";
    exit 3;
}

sub msg { ## no critic

    my $name = shift || '?';

    my $msg = '';

    if (exists $msg{$lang}{$name}) {
        $msg = $msg{$lang}{$name};
    }
    elsif (exists $msg{'en'}{$name}) {
        $msg = $msg{'en'}{$name};
    }
    else {
        ## Allow for non-matches in certain rare cases
        return '' if $opt{nomsgok};
        my $line = (caller)[2];
        die qq{Invalid message "$name" from line $line\n};
    }

    my $x=1;
    {
        my $val = $_[$x-1];
        $val = '?' if ! defined $val;
        last unless $msg =~ s/\$$x/$val/g;
        $x++;
        redo;
    }
    return $msg;

} ## end of msg

sub msgn { ## no critic
    return msg(@_) . "\n";
}

sub msg_en {

    my $name = shift || '?';

    return $msg{'en'}{$name};

} ## end of msg_en

## Everything from here on out needs psql, so find and verify a working version:
if ($NO_PSQL_OPTION) {
    (delete $opt{PGBINDIR} or delete $opt{PSQL}) and ndie msg('opt-psql-restrict');
}
if (! defined $PGBINDIR or ! length $PGBINDIR) {
    if (defined $ENV{PGBINDIR} and length $ENV{PGBINDIR}){
        $PGBINDIR = $ENV{PGBINDIR};
    }
    elsif (defined $opt{PGBINDIR} and length $opt{PGBINDIR}){
        $PGBINDIR = $opt{PGBINDIR};
    }
    else {
        undef $PGBINDIR;
    }
}
if (exists $opt{PSQL}) {
    $PSQL = $opt{PSQL};
    $PSQL =~ m{^/[\w\d\/]*psql$} or ndie msg('opt-psql-badpath');
    -e $PSQL or ndie msg('opt-psql-noexist', $PSQL);
}
else {
    my $psql = (defined $PGBINDIR) ? "$PGBINDIR/psql" : 'psql';
    chomp($PSQL = qx{which "$psql"});
    $PSQL or ndie msg('opt-psql-nofind');
}
-x $PSQL or ndie msg('opt-psql-noexec', $PSQL);
$res = qx{$PSQL --version};
$res =~ /psql\D+(\d+\.\d+)/ or ndie msg('opt-psql-nover');
our $psql_version = $1;

$VERBOSE >= 2 and warn qq{psql=$PSQL version=$psql_version\n};

$opt{defaultdb} = $psql_version >= 8.0 ? 'postgres' : 'template1';
$opt{defaultdb} = 'pgbouncer' if $action =~ /^pgb/;

## Check the current database mode
our $STANDBY = 0;
our $MASTER = 0;
make_sure_standby_mode() if $opt{'assume-standby-mode'};
make_sure_prod() if $opt{'assume-prod'};

## Create the list of databases we are going to connect to
my @targetdb = setup_target_databases();

sub add_response {

    my ($type,$msg) = @_;

    $db->{host} ||= '';

    if ($STANDBY) {
        $action_info->{$action}[0] = 1;
    }

    if ($nohost) {
        push @{$type->{''}} => [$msg, length $nohost > 1 ? $nohost : ''];
        return;
    }

    my $dbservice = $db->{dbservice};
    my $dbname    = defined $db->{dbname} ? qq{DB "$db->{dbname}"} : '';
    my $dbhost    = (!$db->{host} or $db->{host} eq '<none>') ? '' : qq{ (host:$db->{host})};
    my $dbport    = defined $db->{port} ? ($db->{port} eq $opt{defaultport} ? '' : qq{ (port=$db->{port}) }) : '';

    ## Same_schema gets some different output
    my $same_schema_header = '';
    if ($action eq 'same_schema') {

        ## Pretty display of what exactly those numbers mean!
        my $number = 0;
        my $historical = 0;
        for my $row (@targetdb) {
            $number++;
            if (exists $row->{filename}) {
                $historical = 1;
                $same_schema_header .= sprintf "\nDB %s: File=%s\nDB %s: %s: %s  %s: %s",
                    $number,
                    $row->{filename},
                    $number,
                    'Creation date',
                    $row->{ctime},
                    'CP version',
                    $row->{cversion};
            }
            $same_schema_header .= sprintf "\nDB %s: %s%s%s%s%s",
                $number,
                defined $row->{dbservice} ? qq{dbservice=$row->{dbservice} } : '',
                defined $row->{port} ? qq{port=$row->{port} } : '',
                defined $row->{host} ? qq{host=$row->{host} } : '',
                defined $row->{dbname} ? qq{dbname=$row->{dbname} } : '',
                defined $row->{dbuser} ? qq{user=$row->{dbuser} } : '';
            $same_schema_header .= "\nDB $number: PG version: $row->{pgversion}";
            $same_schema_header .= "\nDB $number: Total objects: $row->{objects}";
        }

        ## Databases
        $number = 1;
        my %dlist = map { ($_->{dbname} || ''), $number++; } @targetdb;
        if (keys %dlist > 1 and ! $historical) {
            my $dblist = join ',' => sort { $dlist{$a} <=> $dlist{$b} } keys %dlist;
            $dbname = qq{ (databases:$dblist)};
        }
        ## Hosts
        $number = 1;
        my %hostlist = map { ($_->{host} || ''), $number++; } @targetdb;
        if (keys %hostlist > 1 and ! $historical) {
            my $dblist = join ',' => sort { $hostlist{$a} <=> $hostlist{$b} } keys %hostlist;
            $dbhost = qq{ (hosts:$dblist)};
        }
        ## Ports
        $number = 1;
        my %portlist = map { ($_->{port} || ''), $number++; } @targetdb;
        if (keys %portlist > 1 and ! $historical) {
            my $dblist = join ',' => sort { $portlist{$a} <=> $portlist{$b} } keys %portlist;
            $dbport = qq{ (ports:$dblist)};
        }
    }

    my $header = sprintf q{%s%s%s%s},
        ($action_info->{$action}[0] ? '' : (defined $dbservice and length $dbservice)) ?
        qq{service=$dbservice} : $dbname,
        (defined $db->{showschema} ? qq{ schema:$db->{showschema} } : ''),
        $dbhost,
        $dbport;
    $header =~ s/\s+$//;
    $header =~ s/^ //;
    my $perf = ($opt{showtime} and $db->{totaltime} and $action ne 'bloat') ? "time=$db->{totaltime}s" : '';
    if ($db->{perf}) {
        $db->{perf} =~ s/^ +//;
        if (length $same_schema_header) {
            $db->{perf} =~ s/^\n//;
            $db->{perf} = "$same_schema_header\n$db->{perf}";
        }
        $perf .= sprintf '%s%s', length($perf) ? ' ' : '', $db->{perf};
    }

    ## Strip trailing semicolons as allowed by the Nagios spec
    ## But not for same_schema, where we might have (for example) a view def
    if ($action ne 'same_schema') {
        $perf =~ s/; / /;
        $perf =~ s/;$//;
    }

    push @{$type->{$header}} => [$msg,$perf];

    return;

} ## end of add_response


sub add_unknown {
    my $msg = shift || $db->{error};
    $msg =~ s/[\r\n]\s*/\\n /g;
    $msg =~ s/\|/<PIPE>/g if $opt{showperf};
    add_response \%unknown, $msg;
}
sub add_critical {
    add_response \%critical, shift;
}
sub add_warning {
    add_response \%warning, shift;
}
sub add_ok {
    add_response \%ok, shift;
}


sub do_mrtg {
    ## Hashref of info to pass out for MRTG or stat
    my $arg = shift;
    my $one = $arg->{one} || 0;
    my $two = $arg->{two} || 0;
    if ($SIMPLE) {
        if (! exists $arg->{one}) {
            print "$arg->{msg}\n";
        }
        else {
            $one = $two if (length $two and $two > $one);
            if ($opt{transform} eq 'KB' and $one =~ /^\d+$/) {
                $one = int $one/(1024);
            }
            if ($opt{transform} eq 'MB' and $one =~ /^\d+$/) {
                $one = int $one/(1024*1024);
            }
            elsif ($opt{transform} eq 'GB' and $one =~ /^\d+$/) {
                $one = int $one/(1024*1024*1024);
            }
            elsif ($opt{transform} eq 'TB' and $one =~ /^\d+$/) {
                $one = int $one/(1024*1024*1024*1024);
            }
            elsif ($opt{transform} eq 'EB' and $one =~ /^\d+$/) {
                $one = int $one/(1024*1024*1024*1024*1024);
            }
            print "$one\n";
        }
    }
    else {
        my $uptime = $arg->{uptime} || '';
        my $message = $arg->{msg} || '';
        print "$one\n$two\n$uptime\n$message\n";
    }
    exit 0;
}


sub bad_mrtg {
    my $msg = shift;
    $ERROR and ndie $ERROR;
    warn msgn('mrtg-fail', $action, $msg);
    exit 3;
}


sub do_mrtg_stats {

    ## Show the two highest items for mrtg stats hash

    my $msg = shift;
    defined $msg or ndie('unknown-error');

    if (! keys %stats) {
        if ($SIMPLE) {
            do_mrtg({msg => $msg});
        }
        bad_mrtg($msg);
    }
    my ($one,$two) = ('','');
    for (sort { $stats{$b} <=> $stats{$a} } keys %stats) {
        if ($one eq '') {
            $one = $stats{$_};
            $msg = exists $statsmsg{$_} ? $statsmsg{$_} : "DB: $_";
            next;
        }
        $two = $stats{$_};
        last;
    }
    do_mrtg({one => $one, two => $two, msg => $msg});
}

sub make_sure_mode_is {

    ## Requires $ENV{PGDATA} or --datadir

    $db->{host} = '<none>';

    ## Run pg_controldata, grab the mode
    $res = open_controldata();

    my $regex = msg('checkmode-state');
    if ($res !~ /$regex\s*(.+)/) { ## no critic (ProhibitUnusedCapture)
        ## Just in case, check the English one as well
        $regex = msg_en('checkmode-state');
        if ($res !~ /$regex\s*(.+)/) {
            ndie msg('checkpoint-noregex');
        }
    }
    my $last = $1;

    return $last;

}

sub make_sure_standby_mode {

    ## Checks if database in standby mode
    ## Requires $ENV{PGDATA} or --datadir

    my $last = make_sure_mode_is();

    my $regex = msg('checkmode-recovery');
    if ($last =~ /$regex/) {
        $STANDBY = 1;
    }

    return;

} ## end of make_sure_standby_mode

sub make_sure_prod {

    ## Checks if database in production mode
    ## Requires $ENV{PGDATA} or --datadir

    my $last = make_sure_mode_is();

    my $regex = msg('checkmode-prod');
    if ($last =~ /$regex/) {
        $MASTER = 1;
    }

    return;

} ## end of make_sure_production_mode

sub finishup {

    ## Final output
    ## These are meant to be compact and terse: sometimes messages go to pagers

    if ($MRTG) {
        ## Try hard to ferret out a message in case we short-circuited here
        my $msg = [[]];
        if (keys %critical) {
            ($msg) = values %critical;
        }
        elsif (keys %warning) {
            ($msg) = values %warning;
        }
        elsif (keys %ok) {
            ($msg) = values %ok;
        }
        elsif (keys %unknown) {
            ($msg) = values %unknown;
        }
        do_mrtg_stats($msg->[0][0]);
    }

    $action =~ s/^\s*(\S+)\s*$/$1/;
    my $service = sprintf "%s$action", $FANCYNAME ? 'postgres_' : '';
    if (keys %critical or keys %warning or keys %ok or keys %unknown) {
        ## If in quiet mode, print nothing if all is ok
        if ($opt{quiet} and ! keys %critical and ! keys %warning and ! keys %unknown) {
        }
        else {
            printf '%s ', $YELLNAME ? uc $service : $service;
        }
    }

    sub dumpresult {
        my ($type,$info) = @_;
        my $SEP = ' * ';
        ## Are we showing DEBUG_INFO?
        my $showdebug = 0;
        if ($DEBUGOUTPUT) {
            $showdebug = 1 if $DEBUGOUTPUT =~ /a/io
                or ($DEBUGOUTPUT =~ /c/io and $type eq 'c')
                or ($DEBUGOUTPUT =~ /w/io and $type eq 'w')
                or ($DEBUGOUTPUT =~ /o/io and $type eq 'o')
                or ($DEBUGOUTPUT =~ /u/io and $type eq 'u');
        }
        for (sort keys %$info) {
            printf '%s %s%s ',
                $_,
                $showdebug ? "[DEBUG: $DEBUG_INFO] " : '',
                join $SEP => map { $_->[0] } @{$info->{$_}};
        }
        if ($opt{showperf}) {
            my $pmsg = '';
            for (sort keys %$info) {
                my $m = sprintf '%s ', join ' ' => map { $_->[1] } @{$info->{$_}};
                $pmsg .= $m;
            }
            $pmsg =~ s/^\s+//;
            $pmsg and print "| $pmsg";
        }
        print "\n";

        return;

    }

    if (keys %critical) {
        print 'CRITICAL: ';
        dumpresult(c => \%critical);
        exit 2;
    }
    if (keys %warning) {
        print 'WARNING: ';
        dumpresult(w => \%warning);
        exit 1;
    }
    if (keys %ok) {
        ## We print nothing if in quiet mode
        if (! $opt{quiet}) {
            print 'OK: ';
            dumpresult(o => \%ok);
        }
        exit 0;
    }
    if (keys %unknown) {
        print 'UNKNOWN: ';
        dumpresult(u => \%unknown);
        exit 3;
    }

    die $USAGE;

} ## end of finishup


## For options that take a size e.g. --critical="10 GB"
our $sizere = qr{^\s*(\d+\.?\d?)\s*([bkmgtepz])?\w*$}i; ## Don't care about the rest of the string

## For options that take a time e.g. --critical="10 minutes" Fractions are allowed.
our $timere = qr{^\s*(\d+(?:\.\d+)?)\s*(\w*)\s*$}i;

## For options that must be specified in seconds
our $timesecre = qr{^\s*(\d+)\s*(?:s(?:econd|ec)?)?s?\s*$};

## For simple checksums:
our $checksumre = qr{^[a-f0-9]{32}$};

## If in test mode, verify that we can run each requested action
our %testaction = (
                  autovac_freeze    => 'VERSION: 8.2',
                  last_vacuum       => 'ON: stats_row_level(<8.3) VERSION: 8.2',
                  last_analyze      => 'ON: stats_row_level(<8.3) VERSION: 8.2',
                  last_autovacuum   => 'ON: stats_row_level(<8.3) VERSION: 8.2',
                  last_autoanalyze  => 'ON: stats_row_level(<8.3) VERSION: 8.2',
                  prepared_txns     => 'VERSION: 8.1',
                  database_size     => 'VERSION: 8.1',
                  disabled_triggers => 'VERSION: 8.1',
                  relation_size     => 'VERSION: 8.1',
                  sequence          => 'VERSION: 8.1',
                  table_size        => 'VERSION: 8.1',
                  index_size        => 'VERSION: 8.1',
                  query_time        => 'VERSION: 8.1',
                  txn_time          => 'VERSION: 8.3',
                  wal_files         => 'VERSION: 8.1',
                  archive_ready     => 'VERSION: 8.1',
                  fsm_pages         => 'VERSION: 8.2 MAX: 8.3',
                  fsm_relations     => 'VERSION: 8.2 MAX: 8.3',
                  hot_standby_delay => 'VERSION: 9.0',
                  listener          => 'MAX: 8.4',
);
if ($opt{test}) {
    print msgn('testmode-start');
    my $info = run_command('SELECT name, setting FROM pg_settings');
    my %set; ## port, host, name, user
    for my $db (@{$info->{db}}) {
        if (exists $db->{fail}) {
            (my $err = $db->{error}) =~ s/\s*\n\s*/ \| /g;
            print msgn('testmode-fail', $db->{pname}, $err);
            next;
        }
        print msgn('testmode-ok', $db->{pname});
        for (@{ $db->{slurp} }) {
            $set{$_->{name}} = $_->{setting};
        }
    }
    for my $ac (split /\s+/ => $action) {
        my $limit = $testaction{lc $ac};
        next if ! defined $limit;

        if ($limit =~ /VERSION: ((\d+)\.(\d+))/) {
            my ($rver,$rmaj,$rmin) = ($1,$2,$3);
            for my $db (@{$info->{db}}) {
                next unless exists $db->{ok};
                if ($set{server_version} !~ /((\d+)\.(\d+))/) {
                    print msgn('testmode-nover', $db->{pname});
                    next;
                }
                my ($sver,$smaj,$smin) = ($1,$2,$3);
                if ($smaj < $rmaj or ($smaj==$rmaj and $smin < $rmin)) {
                    print msgn('testmode-norun', $ac, $db->{pname}, $rver, $sver);
                }
                $db->{version} = $sver;
            }
        }

        if ($limit =~ /MAX: ((\d+)\.(\d+))/) {
            my ($rver,$rmaj,$rmin) = ($1,$2,$3);
            for my $db (@{$info->{db}}) {
                next unless exists $db->{ok};
                if ($set{server_version} !~ /((\d+)\.(\d+))/) {
                    print msgn('testmode-nover', $db->{pname});
                    next;
                }
                my ($sver,$smaj,$smin) = ($1,$2,$3);
                if ($smaj > $rmaj or ($smaj==$rmaj and $smin > $rmin)) {
                    print msgn('testmode-norun', $ac, $db->{pname}, $rver, $sver);
                }
            }
        }

        while ($limit =~ /\bON: (\w+)(?:\(([<>=])(\d+\.\d+)\))?/g) {
            my ($setting,$op,$ver) = ($1,$2||'',$3||0);
            for my $db (@{$info->{db}}) {
                next unless exists $db->{ok};
                if ($ver) {
                    next if $op eq '<' and $db->{version} >= $ver;
                    next if $op eq '>' and $db->{version} <= $ver;
                    next if $op eq '=' and $db->{version} != $ver;
                }
                my $val = $set{$setting};
                if ($val ne 'on') {
                    print msgn('testmode-noset', $ac, $db->{pname}, $setting);
                }
            }
        }
    }
    print msgn('testmode-end');
    exit 0;
}

## Expand the list of included/excluded users into a standard format
our $USERWHERECLAUSE = '';
if ($opt{includeuser}) {
    my %userlist;
    for my $user (@{$opt{includeuser}}) {
        for my $u2 (split /,/ => $user) {
            $userlist{$u2}++;
        }
    }
    my $safename;
    if (1 == keys %userlist) {
        ($safename = each %userlist) =~ s/'/''/g;
        $USERWHERECLAUSE = " AND usename = '$safename'";
    }
    else {
        $USERWHERECLAUSE = ' AND usename IN (';
        for my $user (sort keys %userlist) {
            ($safename = $user) =~ s/'/''/g;
            $USERWHERECLAUSE .= "'$safename',";
        }
        chop $USERWHERECLAUSE;
        $USERWHERECLAUSE .= ')';
    }
}
elsif ($opt{excludeuser}) {
    my %userlist;
    for my $user (@{$opt{excludeuser}}) {
        for my $u2 (split /,/ => $user) {
            $userlist{$u2}++;
        }
    }
    my $safename;
    if (1 == keys %userlist) {
        ($safename = each %userlist) =~ s/'/''/g;
        $USERWHERECLAUSE = " AND usename <> '$safename'";
    }
    else {
        $USERWHERECLAUSE = ' AND usename NOT IN (';
        for my $user (sort keys %userlist) {
            ($safename = $user) =~ s/'/''/g;
            $USERWHERECLAUSE .= "'$safename',";
        }
        chop $USERWHERECLAUSE;
        $USERWHERECLAUSE .= ')';
    }
}

## Check number of connections, compare to max_connections
check_backends() if $action eq 'backends';

## Table and index bloat
check_bloat() if $action eq 'bloat';

## Simple connection, warning or critical options
check_connection() if $action eq 'connection';

## Check the commitratio of one or more databases
check_commitratio() if $action eq 'commitratio';

## Check the hitratio of one or more databases
check_hitratio() if $action eq 'hitratio';

## Check the size of one or more databases
check_database_size() if $action eq 'database_size';

## Check local disk_space - local means it must be run from the same box!
check_disk_space() if $action eq 'disk_space';

## Check the size of relations, or more specifically, tables and indexes
check_index_size() if $action eq 'index_size';
check_table_size() if $action eq 'table_size';
check_relation_size() if $action eq 'relation_size';

## Check how long since the last full analyze
check_last_analyze() if $action eq 'last_analyze';

## Check how long since the last full vacuum
check_last_vacuum() if $action eq 'last_vacuum';

## Check how long since the last AUTOanalyze
check_last_analyze('auto') if $action eq 'last_autoanalyze';

## Check how long since the last full AUTOvacuum
check_last_vacuum('auto') if $action eq 'last_autovacuum';

## Check that someone is listening for a specific thing
check_listener() if $action eq 'listener';

## Check number and type of locks
check_locks() if $action eq 'locks';

## Logfile is being written to
check_logfile() if $action eq 'logfile';

## Known query finishes in a good amount of time
check_query_runtime() if $action eq 'query_runtime';

## Check the length of running queries
check_query_time() if $action eq 'query_time';

## Verify that the settings are what we think they should be
check_settings_checksum() if $action eq 'settings_checksum';

## Compare DB time to localtime, alert on number of seconds difference
check_timesync() if $action eq 'timesync';

## Check for transaction ID wraparound in all databases
check_txn_wraparound() if $action eq 'txn_wraparound';

## Compare DB versions. warning = just major.minor, critical = full string
check_version() if $action eq 'version';

## Check the number of WAL files. warning and critical are numbers
check_wal_files() if $action eq 'wal_files';

## Check the number of WAL files ready to archive. warning and critical are numbers
check_archive_ready() if $action eq 'archive_ready';

## Check the replication delay in hot standby setup
check_hot_standby_delay() if $action eq 'hot_standby_delay';

## Check the maximum transaction age of all connections
check_txn_time() if $action eq 'txn_time';

## Check the maximum age of idle in transaction connections
check_txn_idle() if $action eq 'txn_idle';

## Run a custom query
check_custom_query() if $action eq 'custom_query';

## Test of replication
check_replicate_row() if $action eq 'replicate_row';

## Compare database schemas
check_same_schema() if $action eq 'same_schema';

## Check sequence values
check_sequence() if $action eq 'sequence';

## See how close we are to autovacuum_freeze_max_age
check_autovac_freeze() if $action eq 'autovac_freeze';

## See how many pages we have used up compared to max_fsm_pages
check_fsm_pages() if $action eq 'fsm_pages';

## See how many relations we have used up compared to max_fsm_relations
check_fsm_relations() if $action eq 'fsm_relations';

## Spit back info from the pg_stat_database table. Cacti only
check_dbstats() if $action eq 'dbstats';

## Check how long since the last checkpoint
check_checkpoint() if $action eq 'checkpoint';

## Check the Database System Identifier
check_cluster_id() if $action eq 'cluster_id';

## Check for disabled triggers
check_disabled_triggers() if $action eq 'disabled_triggers';

## Check for any prepared transactions
check_prepared_txns() if $action eq 'prepared_txns';

## Make sure Slony is behaving
check_slony_status() if $action eq 'slony_status';

## Verify that the pgbouncer settings are what we think they should be
check_pgbouncer_checksum() if $action eq 'pgbouncer_checksum';

## Check the number of active clients in each pgbouncer pool
check_pgb_pool('cl_active') if $action eq 'pgb_pool_cl_active';

## Check the number of waiting clients in each pgbouncer pool
check_pgb_pool('cl_waiting') if $action eq 'pgb_pool_cl_waiting';

## Check the number of active server connections in each pgbouncer pool
check_pgb_pool('sv_active') if $action eq 'pgb_pool_sv_active';

## Check the number of idle server connections in each pgbouncer pool
check_pgb_pool('sv_idle') if $action eq 'pgb_pool_sv_idle';

## Check the number of used server connections in each pgbouncer pool
check_pgb_pool('sv_used') if $action eq 'pgb_pool_sv_used';

## Check the number of tested server connections in each pgbouncer pool
check_pgb_pool('sv_tested') if $action eq 'pgb_pool_sv_tested';

## Check the number of login server connections in each pgbouncer pool
check_pgb_pool('sv_login') if $action eq 'pgb_pool_sv_login';

## Check the current maximum wait time for client connections in pgbouncer pools
check_pgb_pool('maxwait') if $action eq 'pgb_pool_maxwait';

## Check how many clients are connected to pgbouncer compared to max_client_conn.
check_pgbouncer_backends() if $action eq 'pgbouncer_backends';

check_pgagent_jobs() if $action eq 'pgagent_jobs';

##
## Everything past here does not hit a Postgres database
##
$nohost = 1;

## Check for new versions of check_postgres.pl
check_new_version_cp() if $action eq 'new_version_cp';

## Check for new versions of Postgres
check_new_version_pg() if $action eq 'new_version_pg';

## Check for new versions of Bucardo
check_new_version_bc() if $action eq 'new_version_bc';

## Check for new versions of boxinfo
check_new_version_box() if $action eq 'new_version_box';

## Check for new versions of tail_n_mail
check_new_version_tnm() if $action eq 'new_version_tnm';

finishup();

exit 0;


sub build_symlinks {

    ## Create symlinks to most actions
    $ME =~ /postgres/
        or die msgn('symlink-name');

    my $force = $action =~ /force/ ? 1 : 0;
    for my $action (sort keys %$action_info) {
        my $space = ' ' x ($longname - length $action);
        my $file = "check_postgres_$action";
        if (-l $file) {
            if (!$force) {
                my $source = readlink $file;
                print msgn('symlink-done', $file, $space, $source);
                next;
            }
            print msg('symlink-unlink', $file, $space);
            unlink $file or die msgn('symlink-fail1', $file, $!);
        }
        elsif (-e $file) {
            print msgn('symlink-exists', $file, $space);
            next;
        }

        if (symlink $0, $file) {
            print msgn('symlink-create', $file);
        }
        else {
            print msgn('symlink-fail2', $file, $ME, $!);
        }
    }

    exit 0;

} ## end of build_symlinks


sub pretty_size {

    ## Transform number of bytes to a SI display similar to Postgres' format

    my $bytes = shift;
    my $rounded = shift || 0;

    return "$bytes bytes" if $bytes < 10240;

    my @unit = qw/kB MB GB TB PB EB YB ZB/;

    for my $p (1..@unit) {
        if ($bytes <= 1024**$p) {
            $bytes /= (1024**($p-1));
            return $rounded ?
                sprintf ('%d %s', $bytes, $unit[$p-2]) :
                    sprintf ('%.2f %s', $bytes, $unit[$p-2]);
        }
    }

    return $bytes;

} ## end of pretty_size


sub pretty_time {

    ## Transform number of seconds to a more human-readable format
    ## First argument is number of seconds
    ## Second optional arg is highest transform: s,m,h,d,w
    ## If uppercase, it indicates to "round that one out"

    my $sec = shift;
    my $tweak = shift || '';

    ## Just seconds (< 2:00)
    if ($sec < 120 or $tweak =~ /s/) {
        return sprintf "$sec %s", $sec==1 ? msg('time-second') : msg('time-seconds');
    }

    ## Minutes and seconds (< 60:00)
    if ($sec < 60*60 or $tweak =~ /m/) {
        my $min = int $sec / 60;
        $sec %= 60;
        my $ret = sprintf "$min %s", $min==1 ? msg('time-minute') : msg('time-minutes');
        $sec and $tweak !~ /S/ and $ret .= sprintf " $sec %s", $sec==1 ? msg('time-second') : msg('time-seconds');
        return $ret;
    }

    ## Hours, minutes, and seconds (< 48:00:00)
    if ($sec < 60*60*24*2 or $tweak =~ /h/) {
        my $hour = int $sec / (60*60);
        $sec -= ($hour*60*60);
        my $min = int $sec / 60;
        $sec -= ($min*60);
        my $ret = sprintf "$hour %s", $hour==1 ? msg('time-hour') : msg('time-hours');
        $min and $tweak !~ /M/ and $ret .= sprintf " $min %s", $min==1 ? msg('time-minute') : msg('time-minutes');
        $sec and $tweak !~ /[SM]/ and $ret .= sprintf " $sec %s", $sec==1 ? msg('time-second') : msg('time-seconds');
        return $ret;
    }

    ## Days, hours, minutes, and seconds (< 28 days)
    if ($sec < 60*60*24*28 or $tweak =~ /d/) {
        my $day = int $sec / (60*60*24);
        $sec -= ($day*60*60*24);
        my $our = int $sec / (60*60);
        $sec -= ($our*60*60);
        my $min = int $sec / 60;
        $sec -= ($min*60);
        my $ret = sprintf "$day %s", $day==1 ? msg('time-day') : msg('time-days');
        $our and $tweak !~ /H/     and $ret .= sprintf " $our %s", $our==1 ? msg('time-hour')   : msg('time-hours');
        $min and $tweak !~ /[HM]/  and $ret .= sprintf " $min %s", $min==1 ? msg('time-minute') : msg('time-minutes');
        $sec and $tweak !~ /[HMS]/ and $ret .= sprintf " $sec %s", $sec==1 ? msg('time-second') : msg('time-seconds');
        return $ret;
    }

    ## Weeks, days, hours, minutes, and seconds (< 28 days)
    my $week = int $sec / (60*60*24*7);
    $sec -= ($week*60*60*24*7);
    my $day = int $sec / (60*60*24);
    $sec -= ($day*60*60*24);
    my $our = int $sec / (60*60);
    $sec -= ($our*60*60);
    my $min = int $sec / 60;
    $sec -= ($min*60);
    my $ret = sprintf "$week %s", $week==1 ? msg('time-week') : msg('time-weeks');
    $day and $tweak !~ /D/      and $ret .= sprintf " $day %s", $day==1 ? msg('time-day')    : msg('time-days');
    $our and $tweak !~ /[DH]/   and $ret .= sprintf " $our %s", $our==1 ? msg('time-hour')   : msg('time-hours');
    $min and $tweak !~ /[DHM]/  and $ret .= sprintf " $min %s", $min==1 ? msg('time-minute') : msg('time-minutes');
    $sec and $tweak !~ /[DHMS]/ and $ret .= sprintf " $sec %s", $sec==1 ? msg('time-second') : msg('time-seconds');
    return $ret;

} ## end of pretty_time


sub run_command {

    ## Run a command string against each of our databases using psql
    ## Optional args in a hashref:
    ## "failok" - don't report if we failed
    ## "fatalregex" - allow this FATAL regex through
    ## "target" - use this targetlist instead of generating one
    ## "timeout" - change the timeout from the default of $opt{timeout}
    ## "regex" - the query must match this or we throw an error
    ## "emptyok" - it's okay to not match any rows at all
    ## "version" - alternate SQL for different versions of Postgres
    ## "dbnumber" - connect with this specific entry from @targetdb
    ## "conninfo" - return the connection information string without doing anything

    my $string = shift || '';
    my $arg = shift || {};
    my $info = { command => $string, db => [], hosts => 0 };

    ## First of all check if the server in standby mode, if so end this
    ## with OK status.

    if ($STANDBY) {
        $db->{'totaltime'} = '0.00';
        add_ok msg('mode-standby');
        if ($MRTG) {
            do_mrtg({one => 1});
        }
        finishup();
        exit 0;
    }

    $VERBOSE >= 3 and warn qq{Starting run_command with: $string\n};

    my (%host,$passfile,$passfh,$tempdir,$tempfile,$tempfh,$errorfile,$errfh);
    my $offset = -1;

    ## The final list of targets has been set inside @targetdb

    if (! @targetdb) {
        ndie msg('runcommand-nodb');
    }

    ## Create a temp file to store our results
    my @tempdirargs = (CLEANUP => 1);
    if ($opt{tempdir}) {
        push @tempdirargs => 'DIR', $opt{tempdir};
    }

    $tempdir = tempdir(@tempdirargs);
    ($tempfh,$tempfile) = tempfile('check_postgres_psql.XXXXXXX', SUFFIX => '.tmp', DIR => $tempdir);

    ## Create another one to catch any errors
    ($errfh,$errorfile) = tempfile('check_postgres_psql_stderr.XXXXXXX', SUFFIX => '.tmp', DIR => $tempdir);

    ## Mild cleanup of the query
    $string =~ s/^\s*(.+?)\s*$/$1/s;

    ## Set a statement_timeout, as a last-ditch safety measure
    my $timeout = $arg->{timeout} || $opt{timeout};
    my $dbtimeout = $timeout * 1000;
    if ($action !~ /^pgb/) {
        $string = "BEGIN;SET statement_timeout=$dbtimeout;COMMIT;$string";
    }

    ## Keep track of which database we are on, to allow dbnumber to work
    my $num = 0;

    ## Loop through and run the command on each target database
    for $db (@targetdb) {

        ## Skip this one if we are using dbnumber and this is not our choice
        $num++;
        if ($arg->{dbnumber} and $arg->{dbnumber} != $num) {
            next;
        }
        ## Likewise if we have specified "target" database info and this is not our choice
        if ($arg->{target} and $arg->{target} != $db) {
            next;
        }

        ## Just to keep things clean:
        truncate $tempfh, 0;
        truncate $errfh, 0;

        ## Store this target in the global target list
        push @{$info->{db}}, $db;

        my @args = ('-q', '-t');
        if (defined $db->{dbservice} and length $db->{dbservice}) { ## XX Check for simple names
            $db->{pname} = "service=$db->{dbservice}";
            $ENV{PGSERVICE} = $db->{dbservice};
        }
        else {
            $db->{pname} = 'port=' . ($db->{port} || $opt{defaultport}) . " host=$db->{host} db=$db->{dbname} user=$db->{dbuser}";
        }

        ## If all we want is a connection string, give it and leave now
        if ($arg->{conninfo}) {
            return $db->{pname};
        }

        defined $db->{dbname} and push @args, '-d', $db->{dbname};
        defined $db->{dbuser} and push @args, '-U', $db->{dbuser};
        defined $db->{port} and push @args => '-p', $db->{port};
        if ($db->{host} ne '<none>') {
            push @args => '-h', $db->{host};
            $host{$db->{host}}++; ## For the overall count
        }

        if (defined $db->{dbpass} and length $db->{dbpass}) {
            ## Make a custom PGPASSFILE. Far better to simply use your own .pgpass of course
            ($passfh,$passfile) = tempfile('check_postgres.XXXXXXXX', SUFFIX => '.tmp', DIR => $tempdir);
            $VERBOSE >= 3 and warn msgn('runcommand-pgpass', $passfile);
            $ENV{PGPASSFILE} = $passfile;
            printf $passfh "%s:%s:%s:%s:%s\n",
                $db->{host} eq '<none>' ? '*' : $db->{host}, $db->{port}, $db->{dbname}, $db->{dbuser}, $db->{dbpass};
            close $passfh or ndie msg('file-noclose', $passfile, $!);
        }

        push @args, '-o', $tempfile;
        push @args => '-x';

        ## If we've got different SQL, use this first run to simply grab the version
        ## Then we'll use that info to pick the real query
        if ($arg->{version}) {
            if (!$db->{version}) {
                $arg->{versiononly} = 1;
                $arg->{oldstring} = $string;
                $string = 'SELECT version()';
            }
            else {
                $string = $arg->{oldstring} || $arg->{string};
                for my $row (@{$arg->{version}}) {
                    if ($row !~ s/^([<>]?)(\d+\.\d+)\s+//) {
                        ndie msg('die-badversion', $row);
                    }
                    my ($mod,$ver) = ($1||'',$2);
                    if ($mod eq '>' and $db->{version} > $ver) {
                        $string = $row;
                        last;
                    }
                    if ($mod eq '<' and $db->{version} < $ver) {
                        $string = $row;
                        last;
                    }
                    if ($mod eq '' and $db->{version} eq $ver) {
                        $string = $row;
                    }
                }
                delete $arg->{version};
                $info->{command} = $string;
            }
        }

        local $SIG{ALRM} = sub { die 'Timed out' };
        alarm 0;

        push @args, '-c', $string;

        $VERBOSE >= 3 and warn Dumper \@args;

        my $start = $opt{showtime} ? [gettimeofday()] : 0;
        open my $oldstderr, '>&', \*STDERR or ndie msg('runcommand-nodupe');
        open STDERR, '>', $errorfile or ndie msg('runcommand-noerr');
        eval {
            alarm $timeout;
            $res = system $PSQL => @args;
        };
        my $err = $@;
        alarm 0;
        open STDERR, '>&', $oldstderr or ndie msg('runcommand-noerr');
        close $oldstderr or ndie msg('file-noclose', 'STDERR copy', $!);
        if ($err) {
            if ($err =~ /Timed out/) {
                ndie msg('runcommand-timeout', $timeout);
            }
            else {
                ndie msg('runcommand-err');
            }
        }

        $db->{totaltime} = sprintf '%.2f', $opt{showtime} ? tv_interval($start) : 0;

        if ($res) {
            $db->{fail} = $res;
            $VERBOSE >= 3 and !$arg->{failok} and warn msgn('runcommand-nosys', $res);
            seek $errfh, 0, 0;
            {
                local $/;
                $db->{error} = <$errfh> || '';
                $db->{error} =~ s/\s*$//;
                $db->{error} =~ s/^psql: //;
                $ERROR = $db->{error};
            }

            ## If we are just trying to connect, failed attempts are critical
            if ($action eq 'connection' and $db->{error} =~ /FATAL|could not connect/) {
                $info->{fatal} = 1;
                return $info;
            }

            if ($db->{error} =~ /FATAL/) {
                if (exists $arg->{fatalregex} and $db->{error} =~ /$arg->{fatalregex}/) {
                    $info->{fatalregex} = $db->{error};
                    next;
                }
                else {
                    ndie "$db->{error}";
                }
            }

            if ($db->{error} =~ /statement timeout/) {
                ndie msg('runcommand-timeout', $timeout);
            }

            if ($db->{fail} and !$arg->{failok} and !$arg->{noverify}) {

                ## Check if problem is due to backend being too old for this check
                verify_version();

                if (exists $db->{error}) {
                    ndie $db->{error};
                }

                add_unknown;
                ## Remove it from the returned hash
                pop @{$info->{db}};
            }
        }
        else {
            seek $tempfh, 0, 0;
            {
                local $/;
                $db->{slurp} = <$tempfh>;
            }
            $db->{ok} = 1;

            ## Unfortunately, psql outputs "(No rows)" even with -t and -x
            $db->{slurp} = '' if ! defined $db->{slurp} or index($db->{slurp},'(')==0;

            ## Allow an empty query (no matching rows) if requested
            if ($arg->{emptyok} and $db->{slurp} =~ /^\s*$/o) {
                $arg->{emptyok2} = 1;
            }
            ## If we just want a version, grab it and redo
            if ($arg->{versiononly}) {
                if ($db->{error}) {
                    ndie $db->{error};
                }
                if ($db->{slurp} !~ /(\d+\.\d+)/) {
                    ndie msg('die-badversion', $db->{slurp});
                }
                $db->{version} = $1;
                $db->{ok} = 0;
                delete $arg->{versiononly};
                ## Remove this from the returned hash
                pop @{$info->{db}};
                redo;
            }

            ## If we were provided with a regex, check and bail if it fails
            if ($arg->{regex} and ! $arg->{emptyok2}) {
                if ($db->{slurp} !~ $arg->{regex}) {
                    ## Check if problem is due to backend being too old for this check

                    verify_version();

                    add_unknown msg('invalid-query', $db->{slurp});

                    finishup();
                    exit 0;
                }
            }

            ## Transform psql output into an arrayref of hashes
            my @stuff;
            my $lnum = 0;
            my $lastval;
            for my $line (split /\n/ => $db->{slurp}) {

                if (index($line,'-')==0) {
                    $lnum++;
                    next;
                }
                if ($line =~ /^ ?([\?\w]+)\s+\| (.*?)\s*$/) {
                    $stuff[$lnum]{$1} = $2;
                    $lastval = $1;
                }
                elsif ($line =~ /^ ?QUERY PLAN\s+\| (.*)/) {
                    $stuff[$lnum]{queryplan} = $1;
                    $lastval = 'queryplan';
                }
                elsif ($line =~ /^\s+: (.*)/) {
                    $stuff[$lnum]{$lastval} .= "\n$1";
                }
                elsif ($line =~ /^\s+\| (.+)/) {
                    $stuff[$lnum]{$lastval} .= "\n$1";
                }
                ## No content: can happen in the source of functions, for example
                elsif ($line =~ /^\s+\|\s+$/) {
                    $stuff[$lnum]{$lastval} .= "\n";
                }
                else {
                    my $msg = msg('no-parse-psql');
                    warn "$msg\n";
                    $msg = msg('bug-report');
                    warn "$msg\n";
                    my $cline = (caller)[2];
                    my $args = join ' ' => @args;
                    warn "Version:          $VERSION\n";
                    warn "OS:               $^O\n";
                    warn "Action:           $action\n";
                    warn "Calling line:     $cline\n";
                    warn "Output:           >>$line<<\n";
                    $args =~ s/ -c (.+)/ -c "$1"/s;
                    warn "Command:          $PSQL $args\n";
                    ## Next to last thing is to see if we can grab the PG version
                    if (! $opt{stop_looping}) {
                        ## Just in case...
                        $opt{stop_looping} = 1;
                        my $linfo = run_command('SELECT version() AS version');
                        (my $v = $linfo->{db}[0]{slurp}[0]{version}) =~ s/(\w+ \S+).+/$1/;
                        warn "Postgres version: $v\n";
                    }
                    ## This is a serious parsing fail, so it can be helpful to have the whole enchilada:
                    warn 'Full output: ' . (Dumper $db->{slurp}) . "\n\n";
                    exit 1;
                }
            }
            $db->{slurp} = \@stuff;
        } ## end valid system call

    } ## end each database

    close $errfh or ndie msg('file-noclose', $errorfile, $!);
    close $tempfh or ndie msg('file-noclose', $tempfile, $!);

    eval { File::Temp::cleanup(); };

    $info->{hosts} = keys %host;

    $VERBOSE >= 3 and warn Dumper $info;

    if ($DEBUGOUTPUT) {
        if (defined $info->{db} and defined $info->{db}[0]{slurp}) {
            $DEBUG_INFO = $info->{db}[0]{slurp};
            $DEBUG_INFO =~ s/\n/\\n/g;
            $DEBUG_INFO =~ s/\|/<SEP>/g;
        }
    }

    return $info;

} ## end of run_command


sub setup_target_databases {

    ## Build a list of all databases to connect to.
    ## Returns a list of all such databases with connection information:
    ## -- dbuser, --dbpass, --dbservice, --port, --dbname, --host
    ##
    ## Items are determined by host, port, and db arguments
    ## Multi-args are grouped together: host, port, dbuser, dbpass
    ## Groups are kept together for first pass
    ## The final arg in a group is passed on
    ##
    ## Examples:
    ## --host=a,b --port=5433 --db=c

    ## Connects twice to port 5433, using database c, to hosts a and b
    ## a-5433-c b-5433-c
    ##
    ## --host=a,b --port=5433 --db=c,d
    ## Connects four times: a-5433-c a-5433-d b-5433-c b-5433-d
    ##
    ## --host=a,b --host=foo --port=1234 --port=5433 --db=e,f
    ## Connects six times: a-1234-e a-1234-f b-1234-e b-1234-f foo-5433-e foo-5433-f
    ##
    ## --host=a,b --host=x --port=5432,5433 --dbuser=alice --dbuser=bob --db=baz
    ## Connects three times: a-5432-alice-baz b-5433-alice-baz x-5433-bob-baz

    ## Returns a list of targets as a hashref

    my $arg = shift || {};

    ## The final list of targets:
    my @target;

    ## Default connection options
    my $conn =
        {
         host   =>    [$ENV{PGHOST}     || '<none>'],
         port   =>    [$ENV{PGPORT}     || $opt{defaultport}],
         dbname =>    [$ENV{PGDATABASE} || $opt{defaultdb}],
         dbuser =>    [$ENV{PGUSER}     || $opt{defaultuser}],
         dbpass =>    [$ENV{PGPASSWORD} || ''],
         dbservice => [''],
          };

    ## Don't set any default values if a service is being used
    if (defined $opt{dbservice} and defined $opt{dbservice}->[0] and length $opt{dbservice}->[0]) {
        $conn->{dbname} = [];
        $conn->{port} = [];
        $conn->{dbuser} = [];
    }

    ## If we were passed in a target, use that and move on
    if (exists $arg->{target}) {
        ## Make a copy, in case we are passed in a ref
        my $newtarget;
        for my $key (keys %$conn) {
            $newtarget->{$key} = exists $arg->{target}{$key} ? $arg->{target}{$key} : $conn->{$key};
        }
        return [$newtarget];
    }

    ## Global count of total places we are connecting to
    ## We don't mess with this if using {target} above
    $opt{numdbs} = 0;

    ## The current group number we are looking at
    my $group_num = 0;

    GROUP: {

        ## This level controls a "group" of targets

        ## Start bubbling all our targets into other stuff
        my %group;
        my $found_new_var = 0;

        for my $v (keys %$conn) { ## For each connection var such as port, host...
            my $vname = $v;

            ## Check if something exists at the current slot number for this var
            if (defined $opt{$v}->[$group_num]) {

                my $new = $opt{$v}->[$group_num];

                ## Strip out whitespace unless this is a service or host
                $new =~ s/\s+//g unless $vname eq 'dbservice' or $vname eq 'host';

                ## Set this as the new default for this connection var moving forward
                $conn->{$vname} = [split /,/ => $new];

                ## Make a note that we found something new this round
                $found_new_var = 1;
            }

            $group{$vname} = $conn->{$vname};
        }

        ## If we found nothing new, we must be done building our groups
        last GROUP if ! $found_new_var and @target;

        $group_num++;

        ## Now break the newly created group into individual targets
        my $tbin = 0;
        TARGET: {
            my $foundtarget = 0;
            my %temptarget;
            for my $g (keys %group) {
                if (defined $group{$g}->[$tbin]) {
                    $conn->{$g} = [$group{$g}->[$tbin]];
                    $foundtarget = 1;
                }
                $temptarget{$g} = $conn->{$g}[0];
            }

            ## Leave if nothing new
            last TARGET if ! $foundtarget;

            ## Add to our master list
            push @target => \%temptarget;

            $tbin++;

            redo TARGET;

        } ## end TARGET

        last GROUP if ! $found_new_var;

        redo GROUP;

    } ## end GROUP

    return @target;

} ## end of setup_target_databases


sub verify_version {

    ## Check if the backend can handle the current action
    my $limit = $testaction{lc $action} || '';

    my $versiononly = shift || 0;

    return if ! $limit and ! $versiononly;

    ## We almost always need the version, so just grab it for any limitation
    $SQL = q{SELECT setting FROM pg_settings WHERE name = 'server_version'};
    my $oldslurp = $db->{slurp} || '';
    my $info = run_command($SQL, {noverify => 1});
    if (defined $info->{db}[0]
        and exists $info->{db}[0]{error}
        and defined $info->{db}[0]{error}
        ) {
        ndie $info->{db}[0]{error};
    }

    if (!defined $info->{db}[0] or $info->{db}[0]{slurp}[0]{setting} !~ /((\d+)\.(\d+))/) {
        ndie msg('die-badversion', $SQL);
    }
    my ($sver,$smaj,$smin) = ($1,$2,$3);

    if ($versiononly) {
        return $sver;
    }

    if ($limit =~ /VERSION: ((\d+)\.(\d+))/) {
        my ($rver,$rmaj,$rmin) = ($1,$2,$3);
        if ($smaj < $rmaj or ($smaj==$rmaj and $smin < $rmin)) {
            ndie msg('die-action-version', $action, $rver, $sver);
        }
    }

    while ($limit =~ /\bON: (\w+)(?:\(([<>=])(\d+\.\d+)\))?/g) {
        my ($setting,$op,$ver) = ($1,$2||'',$3||0);
        if ($ver) {
            next if $op eq '<' and $sver >= $ver;
            next if $op eq '>' and $sver <= $ver;
            next if $op eq '=' and $sver != $ver;
        }

        $SQL = qq{SELECT setting FROM pg_settings WHERE name = '$setting'};
        my $info2 = run_command($SQL);
        if (!defined $info2->{db}[0]) {
            ndie msg('die-nosetting', $setting);
        }
        my $val = $info2->{db}[0]{slurp}[0]{setting};
        if ($val !~ /^\s*on\b/) {
            ndie msg('die-noset', $action, $setting);
        }
    }

    $db->{slurp} = $oldslurp;
    return;

} ## end of verify_version


sub size_in_bytes { ## no critic (RequireArgUnpacking)

    ## Given a number and a unit, return the number of bytes.
    ## Defaults to bytes

    my ($val,$unit) = ($_[0],lc substr($_[1]||'s',0,1));
    return $val * ($unit eq 'b' ? 1 : $unit eq 'k' ? 1024 : $unit eq 'm' ? 1024**2 :
                    $unit eq 'g' ? 1024**3 : $unit eq 't' ? 1024**4 :
                    $unit eq 'p' ? 1024**5 : $unit eq 'e' ? 1024**6 :
                    $unit eq 'z' ? 1024**7 : 1);

} ## end of size_in_bytes


sub size_in_seconds {

    my ($string,$type) = @_;

    return '' if ! length $string;
    if ($string !~ $timere) {
        ndie msg('die-badtime', $type, substr($type,0,1));
    }
    my ($val,$unit) = ($1,lc substr($2||'s',0,1));
    my $tempval = sprintf '%.9f', $val * (
        $unit eq 's' ?        1 :
        $unit eq 'm' ?       60 :
        $unit eq 'h' ?     3600 :
        $unit eq 'd' ?    86400 :
        $unit eq 'w' ?   604800 :
        $unit eq 'y' ? 31536000 :
            ndie msg('die-badtime', $type, substr($type,0,1))
    );
    $tempval =~ s/0+$//;
    $tempval = int $tempval if $tempval =~ /\.$/;
    return $tempval;

} ## end of size_in_seconds


sub skip_item {

    ## Determine if something should be skipped due to inclusion/exclusion options
    ## Exclusion checked first: inclusion can pull it back in.
    my $name = shift;
    my $schema = shift || '';

    my $stat = 0;
    ## Is this excluded?
    if (defined $opt{exclude}) {
        $stat = 1;
        for (@{$opt{exclude}}) {
            for my $ex (split /\s*,\s*/o => $_) {
                if ($ex =~ s/\.$//) {
                    if ($ex =~ s/^~//) {
                        ($stat += 2 and last) if $schema =~ /$ex/;
                    }
                    else {
                        ($stat += 2 and last) if $schema eq $ex;
                    }
                }
                elsif ($ex =~ s/^~//) {
                    ($stat += 2 and last) if $name =~ /$ex/;
                }
                else {
                    ($stat += 2 and last) if $name eq $ex;
                }
            }
        }
    }
    if (defined $opt{include}) {
        $stat += 4;
        for (@{$opt{include}}) {
            for my $in (split /\s*,\s*/o => $_) {
                if ($in =~ s/\.$//) {
                    if ($in =~ s/^~//) {
                        ($stat += 8 and last) if $schema =~ /$in/;
                    }
                    else {
                        ($stat += 8 and last) if $schema eq $in;
                    }
                }
                elsif ($in =~ s/^~//) {
                    ($stat += 8 and last) if $name =~ /$in/;
                }
                else {
                    ($stat += 8 and last) if $name eq $in;
                }
            }
        }
    }

    ## Easiest to state the cases when we DO skip:
    return 1 if
        3 == $stat     ## exclude matched, no inclusion checking
        or 4 == $stat  ## include check only, no match
        or 7 == $stat; ## exclude match, no inclusion match

    return 0;

} ## end of skip_item


sub validate_range {

    ## Valid that warning and critical are set correctly.
    ## Returns new values of both

    my $arg = shift;
    defined $arg and ref $arg eq 'HASH' or ndie qq{validate_range must be called with a hashref\n};

    return ('','') if $MRTG and !$arg->{forcemrtg};

    my $type = $arg->{type} or ndie qq{validate_range must be provided a 'type'\n};

    ## The 'default default' is an empty string, which should fail all mandatory tests
    ## We only set the 'arg' default if neither option is provided.
    my $warning  = exists $opt{warning}  ? $opt{warning} :
        exists $opt{critical} ? '' : $arg->{default_warning} || '';
    my $critical = exists $opt{critical} ? $opt{critical} :
        exists $opt{warning} ? '' : $arg->{default_critical} || '';

    if ('string' eq $type) {
        ## Don't use this unless you have to
    }
    elsif ('seconds' eq $type) {
        if (length $warning) {
            if ($warning !~ $timesecre) {
                ndie msg('range-seconds', 'warning');
            }
            $warning = $1;
        }
        if (length $critical) {
            if ($critical !~ $timesecre) {
                ndie msg('range-seconds', 'critical')
            }
            $critical = $1;
            if (!$arg->{any_warning} and length $warning and $warning > $critical) {
                ndie msg('range-warnbigtime', $warning, $critical);
            }
        }
    }
    elsif ('time' eq $type) {
        $critical = size_in_seconds($critical, 'critical');
        $warning = size_in_seconds($warning, 'warning');
        if (! length $critical and ! length $warning) {
            ndie msg('range-notime');
        }
        if (!$arg->{any_warning} and length $warning and length $critical and $warning > $critical) {
            ndie msg('range-warnbigtime', $warning, $critical);
        }
    }
    elsif ('version' eq $type) {
        my $msg = msg('range-version');
        if (length $warning and $warning !~ /^\d+\.\d+\.?[\d\w]*$/) {
            ndie msg('range-badversion', 'warning', $msg);
        }
        if (length $critical and $critical !~ /^\d+\.\d+\.?[\d\w]*$/) {
            ndie msg('range-badversion', 'critical', $msg);
        }
        if (! length $critical and ! length $warning) {
            ndie msg('range-noopt-orboth');
        }
    }
    elsif ('size' eq $type) {
        if (length $critical) {
            if ($critical !~ $sizere) {
                ndie msg('range-badsize', 'critical');
            }
            $critical = size_in_bytes($1,$2);
        }
        if (length $warning) {
            if ($warning !~ $sizere) {
                ndie msg('range-badsize', 'warning');
            }
            $warning = size_in_bytes($1,$2);
            if (!$arg->{any_warning} and length $critical and $warning > $critical) {
                ndie msg('range-warnbigsize', $warning, $critical);
            }
        }
        elsif (!length $critical) {
            ndie msg('range-nosize');
        }
    }
    elsif ($type =~ /integer/) {
        $warning =~ s/_//g;
        if (length $warning and $warning !~ /^[-+]?\d+$/) {
            ndie $type =~ /positive/ ? msg('range-int-pos', 'warning') : msg('range-int', 'warning');
        }
        elsif (length $warning and $type =~ /positive/ and $warning <= 0) {
            ndie msg('range-int-pos', 'warning');
        }

        $critical =~ s/_//g;
        if (length $critical and $critical !~ /^[-+]?\d+$/) {
            ndie $type =~ /positive/ ? msg('range-int-pos', 'critical') : msg('range-int', 'critical');
        }
        elsif (length $critical and $type =~ /positive/ and $critical <= 0) {
            ndie msg('range-int-pos', 'critical');
        }

        if (length $warning
            and length $critical
            and (
                ($opt{reverse} and $warning < $critical)
                or
                (!$opt{reverse} and $warning > $critical)
                )
            ) {
            ndie msg('range-warnbig');
        }
        if ($type !~ /string/) {
            $warning = int $warning if length $warning;
            $critical = int $critical if length $critical;
        }
    }
    elsif ('restringex' eq $type) {
        if (! length $critical and ! length $warning) {
            ndie msg('range-noopt-one');
        }
        if (length $critical and length $warning) {
            ndie msg('range-noopt-only');
        }
        my $string = length $critical ? $critical : $warning;
        my $regex = ($string =~ s/^~//) ? '~' : '=';
        $string =~ /^\w+$/ or ndie msg('invalid-option');
    }
    elsif ('percent' eq $type) {
        if (length $critical) {
            if ($critical !~ /^(\d+)\%$/) {
                ndie msg('range-badpercent', 'critical');
            }
            $critical = $1;
        }
        if (length $warning) {
            if ($warning !~ /^(\d+)\%$/) {
                ndie msg('range-badpercent', 'warning');
            }
            $warning = $1;
        }
    }
    elsif ('size or percent' eq $type) {
        if (length $critical) {
            if ($critical =~ $sizere) {
                $critical = size_in_bytes($1,$2);
            }
            elsif ($critical !~ /^\d+\%$/) {
                ndie msg('range-badpercsize', 'critical');
            }
        }
        if (length $warning) {
            if ($warning =~ $sizere) {
                $warning = size_in_bytes($1,$2);
            }
            elsif ($warning !~ /^\d+\%$/) {
                ndie msg('range-badpercsize', 'warning');
            }
        }
        elsif (! length $critical) {
            ndie msg('range-noopt-size');
        }
    }
    elsif ('checksum' eq $type) {
        if (length $critical and $critical !~ $checksumre and $critical ne '0') {
            ndie msg('range-badcs', 'critical');
        }
        if (length $warning and $warning !~ $checksumre) {
            ndie msg('range-badcs', 'warning');
        }
    }
    elsif ('multival' eq $type) { ## Simple number, or foo=#;bar=#
        ## Note: only used for check_locks
        my %err;
        while ($critical =~ /(\w+)\s*=\s*(\d+)/gi) {
            my ($name,$val) = (lc $1,$2);
            $name =~ s/lock$//;
            $err{$name} = $val;
        }
        if (keys %err) {
            $critical = \%err;
        }
        elsif (length $critical and $critical =~ /^(\d+)$/) {
            $err{total} = $1;
            $critical = \%err;
        }
        elsif (length $critical) {
            ndie msg('range-badlock', 'critical');
        }
        my %warn;
        while ($warning =~ /(\w+)\s*=\s*(\d+)/gi) {
            my ($name,$val) = (lc $1,$2);
            $name =~ s/lock$//;
            $warn{$name} = $val;
        }
        if (keys %warn) {
            $warning = \%warn;
        }
        elsif (length $warning and $warning =~ /^(\d+)$/) {
            $warn{total} = $1;
            $warning = \%warn;
        }
        elsif (length $warning) {
            ndie msg('range-badlock', 'warning');
        }
    }
    elsif ('cacti' eq $type) { ## Takes no args, just dumps data
        if (length $warning or length $critical) {
            ndie msg('range-cactionly');
        }
    }
    else {
        ndie msg('range-badtype', $type);
    }

    if ($arg->{both}) {
        if (! length $warning or ! length $critical) {
            ndie msg('range-noopt-both');
        }
    }
    if ($arg->{leastone}) {
        if (! length $warning and ! length $critical) {
            ndie msg('range-noopt-one');
        }
    }
    elsif ($arg->{onlyone}) {
        if (length $warning and length $critical) {
            ndie msg('range-noopt-only');
        }
        if (! length $warning and ! length $critical) {
            ndie msg('range-noopt-one');
        }
    }

    return ($warning,$critical);

} ## end of validate_range


sub validate_size_or_percent_with_oper {

    my $arg = shift || {};
    ndie qq{validate_range must be called with a hashref\n}
        unless ref $arg eq 'HASH';

    my $warning  = exists $opt{warning}  ? $opt{warning} :
        exists $opt{critical} ? '' : $arg->{default_warning} || '';
    my $critical = exists $opt{critical} ? $opt{critical} :
        exists $opt{warning} ? '' : $arg->{default_critical} || '';

    ndie msg('range-noopt-size') unless length $critical || length $warning;
    my @subs;
    for my $val ($warning, $critical) {
        if ($val =~ /^(.+?)\s([&|]{2}|and|or)\s(.+)$/i) {
            my ($l, $op, $r) = ($1, $2, $3);
            local $opt{warning} = $l;
            local $opt{critical} = 0;
            ($l) = validate_range({ type => 'size or percent' });
            $opt{warning} = $r;
            ($r) = validate_range({ type => 'size or percent' });
            if ($l =~ s/%$//) {
                ($l, $r) = ($r, $l);
            }
            else {
                $r =~ s/%$//;
            }
            push @subs, $op eq '&&' || lc $op eq 'and' ? sub {
                $_[0] >= $l && $_[1] >= $r;
            } : sub {
                $_[0] >= $l || $_[1] >= $r;
            };
        }
        else {
            local $opt{warning} = $val;
            local $opt{critical} = 0;
            my ($v) = validate_range({ type => 'size or percent' });
            push @subs, !length $v ? sub { 0 }
                    : $v =~ s/%$// ? sub { $_[1] >= $v }
                                   : sub { $_[0] >= $v };
        }
    }

    return @subs;

} ## end of validate_size_or_percent_with_oper


sub validate_integer_for_time {
    # Used for txn_idle and hot_standby_delay
    # txn_idle, et. al, use the form "$count for $interval"
    # hot_standby_delay appears as "$bytes and $interval"

    my $arg = shift || {};
    ndie qq{validate_integer_for_time must be called with a hashref\n}
        unless ref $arg eq 'HASH';

    my $warning  = exists $opt{warning}  ? $opt{warning} :
        exists $opt{critical} ? '' : $arg->{default_warning} || '';
    my $critical = exists $opt{critical} ? $opt{critical} :
        exists $opt{warning} ? '' : $arg->{default_critical} || '';
    ndie msg('range-nointfortime', 'critical') unless length $critical or length $warning;

    my @ret;
    for my $spec ([ warning => $warning], [critical => $critical]) {
        my ($level, $val) = @{ $spec };
        if (length $val) {
            if ($val =~ /^(.+?)\s(?:for|and)\s(.+)$/i) {
                my ($int, $time) = ($1, $2);

                # Integer first, time second.
                ($int, $time) = ($time, $int)
                    if $int =~ /[a-zA-Z]$/ || $time =~ /^[-+]\d+$/;

                # Determine the values.
                $time = size_in_seconds($time, $level);
                ndie msg('range-int', $level) if $time !~ /^[-+]?\d+$/;
                push @ret, int $int, $time;
            }
            else {
                # Disambiguate int from time int by sign.
                if (($val =~ /^[-+]\d+$/) || ($val =~ /^\d+$/ && $arg->{default_to_int})) {
                    ndie msg('range-int', $level) if $val !~ /^[-+]?\d+$/;
                    push @ret, int $val, '';
                }
                else {
                    # Assume time for backwards compatibility.
                    push @ret, '', size_in_seconds($val, $level);
                }
            }
        }
        else {
            push @ret, '', '';
        }
    }

    return @ret;

} ## end of validate_integer_for_time


sub perfname {

    ## Return a safe label name for Nagios performance data
    my $name = shift;

    my $escape = 0;

    $name =~ s/'/''/g and $escape++;

    if ($escape or index($name, ' ') >=0) {
        $name = qq{'$name'};
    }

    return $name;

} ## end of perfname;


sub open_controldata {
    ## Requires $ENV{PGDATA} or --datadir

    ## Find the data directory, make sure it exists
    my $dir = $opt{datadir} || $ENV{PGDATA};

    if (!defined $dir or ! length $dir) {
        ndie msg('checkpoint-nodir');
    }

    if (! -d $dir) {
        ndie msg('checkpoint-baddir', $dir);
    }

    ## Run pg_controldata
    ## We still catch deprecated option
    my $pgc;
    if (defined $ENV{PGCONTROLDATA} and length $ENV{PGCONTROLDATA}) {
        # ndie msg('depr-pgcontroldata');
        $pgc = "$ENV{PGCONTROLDATA}";
    }
    else {
        $pgc = (defined $PGBINDIR) ? "$PGBINDIR/pg_controldata" : 'pg_controldata';
        chomp($pgc = qx{which "$pgc"});
    }
    -x $pgc or ndie msg('opt-psql-noexec', $pgc);

    $COM = qq{$pgc "$dir"};
    eval {
        $res = qx{$COM 2>&1};
    };
    if ($@) {
        ndie msg('checkpoint-nosys', $@);
    }

    ## If the path is echoed back, we most likely have an invalid data dir
    if ($res =~ /$dir/) {
        ndie msg('checkpoint-baddir2', $dir);
    }

    if ($res =~ /WARNING: Calculated CRC checksum/) {
        ndie msg('checkpoint-badver', $dir);
    }
    if ($res !~ /^pg_control.+\d+/) {
        ndie msg('checkpoint-badver2');
    }

    ## return the pg_controldata output
    return $res;
}


sub check_archive_ready {

    ## Check on the number of WAL archive with status "ready"
    ## Supports: Nagios, MRTG
    ## Must run as a superuser
    ## Critical and warning are the number of files
    ## Example: --critical=10

    return check_wal_files('/archive_status', '.ready', 10, 15);

} ## end of check_archive_ready


sub check_autovac_freeze {

    ## Check how close all databases are to autovacuum_freeze_max_age
    ## Supports: Nagios, MRTG
    ## It makes no sense to run this more than once on the same cluster
    ## Warning and criticals are percentages
    ## Can also ignore databases with exclude, and limit with include

    my ($warning, $critical) = validate_range
        ({
          type              => 'percent',
          default_warning   => '90%',
          default_critical  => '95%',
          forcemrtg         => 1,
          });

    (my $w = $warning) =~ s/\D//;
    (my $c = $critical) =~ s/\D//;

    my $SQL = q{SELECT freez, txns, ROUND(100*(txns/freez::float)) AS perc, datname}.
        q{ FROM (SELECT foo.freez::int, age(datfrozenxid) AS txns, datname}.
        q{ FROM pg_database d JOIN (SELECT setting AS freez FROM pg_settings WHERE name = 'autovacuum_freeze_max_age') AS foo}.
        q{ ON (true) WHERE d.datallowconn) AS foo2 ORDER BY 3 DESC, 4 ASC};

    my $info = run_command($SQL, {regex => qr{\w+} } );

    $db = $info->{db}[0];

    my (@crit,@warn,@ok);
    my ($maxp,$maxt,$maxdb) = (0,0,''); ## used by MRTG only
  SLURP: for my $r (@{$db->{slurp}}) {
        next SLURP if skip_item($r->{datname});

        if ($MRTG) {
            if ($r->{perc} > $maxp) {
                $maxdb = $r->{datname};
                $maxp = $r->{perc};
            }
            elsif ($r->{perc} == $maxp) {
                $maxdb .= sprintf '%s%s', (length $maxdb ? ' | ' : ''), $r->{datname};
            }
            $maxt = $r->{txns} if $r->{txns} > $maxt;
            next SLURP;
        }

        my $msg = sprintf ' %s=%s%%;%s;%s', perfname($r->{datname}), $r->{perc}, $w, $c;
        $db->{perf} .= " $msg";
        if (length $critical and $r->{perc} >= $c) {
            push @crit => $msg;
        }
        elsif (length $warning and $r->{perc} >= $w) {
            push @warn => $msg;
        }
        else {
            push @ok => $msg;
        }
    }
    if ($MRTG) {
        do_mrtg({one => $maxp, two => $maxt, msg => $maxdb});
    }
    if (@crit) {
        add_critical join ' ' => @crit;
    }
    elsif (@warn) {
        add_warning join ' ' => @warn;
    }
    else {
        add_ok join ' ' => @ok;
    }

    return;

} ## end of check_autovac_freeze


sub check_backends {

    ## Check the number of connections
    ## Supports: Nagios, MRTG
    ## It makes no sense to run this more than once on the same cluster
    ## Need to be superuser, else only your queries will be visible
    ## Warning and criticals can take three forms:
    ## critical = 12 -- complain if there are 12 or more connections
    ## critical = 95% -- complain if >= 95% of available connections are used
    ## critical = -5 -- complain if there are only 5 or fewer connection slots left
    ## The former two options only work with simple numbers - no percentage or negative
    ## Can also ignore databases with exclude, and limit with include

    my $warning  = $opt{warning}  || '90%';
    my $critical = $opt{critical} || '95%';
    my $noidle   = $opt{noidle}   || 0;

    ## If only critical was used, remove the default warning
    if ($opt{critical} and !$opt{warning}) {
        $warning = $critical;
    }

    my $validre = qr{^(\-?)(\d+)(\%?)$};
    if ($critical !~ $validre) {
        ndie msg('backends-users', 'Critical');
    }
    my ($e1,$e2,$e3) = ($1,$2,$3);
    if ($warning !~ $validre) {
        ndie msg('backends-users', 'Warning');
    }
    my ($w1,$w2,$w3) = ($1,$2,$3);

    ## If number is greater, all else is same, and not minus
    if ($w2 > $e2 and $w1 eq $e1 and $w3 eq $e3 and $w1 eq '') {
        ndie msg('range-warnbig');
    }
    ## If number is less, all else is same, and minus
    if ($w2 < $e2 and $w1 eq $e1 and $w3 eq $e3 and $w1 eq '-') {
        ndie msg('range-warnsmall');
    }
    if (($w1 and $w3) or ($e1 and $e3)) {
        ndie msg('range-neg-percent');
    }

    my $MAXSQL = q{SELECT setting AS mc FROM pg_settings WHERE name = 'max_connections'};

    my $NOIDLE = $noidle ? q{WHERE current_query <> '<IDLE>'} : '';
    $SQL = qq{
SELECT COUNT(datid) AS current,
  ($MAXSQL) AS mc,
  d.datname
FROM pg_database d
LEFT JOIN pg_stat_activity s ON (s.datid = d.oid) $NOIDLE
GROUP BY 2,3
ORDER BY datname
};
    my $SQL92;
    ($SQL92 = $SQL) =~ s/current_query <> '<IDLE>'/state <> 'idle'/g;
    my $info = run_command($SQL, {regex => qr{\d+}, fatalregex => 'too many clients', version => [">9.1 $SQL92"] } );

    $db = $info->{db}[0];

    ## If we cannot connect because of too many clients, we treat as a critical error
    if (exists $info->{fatalregex}) {
        my $regmsg = msg('backends-po');
        my $regmsg2 = msg_en('backends-po');
        if ($info->{fatalregex} =~ /$regmsg/ or $info->{fatalregex} =~ /$regmsg2/) {
            add_critical msg('backends-fatal');
            return;
        }
    }

    ## There may be no entries returned if we catch pg_stat_activity at the right
    ## moment in older versions of Postgres
    if (! defined $db) {
        $info = run_command($MAXSQL, {regex => qr[\d] } );
        $db = $info->{db}[0];
        if (!defined $db->{slurp} or $db->{slurp} !~ /(\d+)/) {
            undef %unknown;
            add_unknown msg('backends-nomax');
            return;
        }
        my $limit = $1;
        if ($MRTG) {
            do_mrtg({one => 1, msg => msg('backends-mrtg', $db->{dbname}, $limit)});
        }
        my $percent = (int 1/$limit*100) || 1;
        add_ok msg('backends-msg', 1, $limit, $percent);
        return;
    }

    my $total = 0;
    my $grandtotal = @{$db->{slurp}};

    ## If no max_connections, something is wrong
    if ($db->{slurp}[0]{mc} !~ /\d/) {
        add_unknown msg('backends-nomax');
        return;
    }
    my $limit = $db->{slurp}[0]{mc};

    for my $r (@{$db->{slurp}}) {

        ## Always want perf to show all
        my $nwarn=$w2;
        my $ncrit=$e2;
        if ($e1) {
            $ncrit = $limit-$e2;
        }
        elsif ($e3) {
            $ncrit = (int $e2*$limit/100);
        }
        if ($w1) {
            $nwarn = $limit-$w2;
        }
        elsif ($w3) {
            $nwarn = (int $w2*$limit/100)
        }

        if (! skip_item($r->{datname})) {
            $db->{perf} .= sprintf ' %s=%s;%s;%s;0;%s',
                perfname($r->{datname}), $r->{current}, $nwarn, $ncrit, $limit;
            $total += $r->{current};
        }
    }

    if ($MRTG) {
        do_mrtg({one => $total, msg => msg('backends-mrtg', $db->{dbname}, $limit)});
    }

    if (!$total) {
        if ($grandtotal) {
            ## We assume that exclude/include rules are correct, and we simply had no entries
            ## at all in the specific databases we wanted
            add_ok msg('backends-oknone');
        }
        else {
            add_unknown msg('no-match-db');
        }
        return;
    }

    my $percent = (int $total / $limit*100) || 1;
    my $msg = msg('backends-msg', $total, $limit, $percent);
    my $ok = 1;

    if ($e1) { ## minus
        $ok = 0 if $limit-$total <= $e2;
    }
    elsif ($e3) { ## percent
        my $nowpercent = $total/$limit*100;
        $ok = 0 if $nowpercent >= $e2;
    }
    else { ## raw number
        $ok = 0 if $total >= $e2;
    }
    if (!$ok) {
        add_critical $msg;
        return;
    }

    if ($w1) {
        $ok = 0 if $limit-$total <= $w2;
    }
    elsif ($w3) {
        my $nowpercent = $total/$limit*100;
        $ok = 0 if $nowpercent >= $w2;
    }
    else {
        $ok = 0 if $total >= $w2;
    }
    if (!$ok) {
        add_warning $msg;
        return;
    }

    add_ok $msg;

    return;

} ## end of check_backends


sub check_bloat {

    ## Check how bloated the tables and indexes are
    ## Supports: Nagios, MRTG
    ## NOTE! This check depends on ANALYZE being run regularly
    ## Also requires stats collection to be on
    ## This action may be very slow on large databases
    ## By default, checks all relations
    ## Can check specific one(s) with include; can ignore some with exclude
    ## Begin name with a '~' to make it a regular expression
    ## Warning and critical are in sizes, defaults to bytes
    ## Valid units: b, k, m, g, t, e
    ## All above may be written as plural or with a trailing 'b'
    ## Example: --critical="25 GB" --include="mylargetable"
    ## Can also specify percentages

    ## Don't bother with tables or indexes unless they have at least this many bloated pages
    my $MINPAGES = 0;
    my $MINIPAGES = 10;

    my $LIMIT = 10;
    if ($opt{perflimit}) {
        $LIMIT = $opt{perflimit};
    }

    my ($warning, $critical) = validate_size_or_percent_with_oper
        ({
          default_warning    => '1 GB',
          default_critical   => '5 GB',
          });

    ## This was fun to write
    $SQL = q{
SELECT
  current_database() AS db, schemaname, tablename, reltuples::bigint AS tups, relpages::bigint AS pages, otta,
  ROUND(CASE WHEN otta=0 OR sml.relpages=0 OR sml.relpages=otta THEN 0.0 ELSE sml.relpages/otta::numeric END,1) AS tbloat,
  CASE WHEN relpages < otta THEN 0 ELSE relpages::bigint - otta END AS wastedpages,
  CASE WHEN relpages < otta THEN 0 ELSE bs*(sml.relpages-otta)::bigint END AS wastedbytes,
  CASE WHEN relpages < otta THEN '0 bytes'::text ELSE (bs*(relpages-otta))::bigint || ' bytes' END AS wastedsize,
  iname, ituples::bigint AS itups, ipages::bigint AS ipages, iotta,
  ROUND(CASE WHEN iotta=0 OR ipages=0 OR ipages=iotta THEN 0.0 ELSE ipages/iotta::numeric END,1) AS ibloat,
  CASE WHEN ipages < iotta THEN 0 ELSE ipages::bigint - iotta END AS wastedipages,
  CASE WHEN ipages < iotta THEN 0 ELSE bs*(ipages-iotta) END AS wastedibytes,
  CASE WHEN ipages < iotta THEN '0 bytes' ELSE (bs*(ipages-iotta))::bigint || ' bytes' END AS wastedisize,
  CASE WHEN relpages < otta THEN
    CASE WHEN ipages < iotta THEN 0 ELSE bs*(ipages-iotta::bigint) END
    ELSE CASE WHEN ipages < iotta THEN bs*(relpages-otta::bigint)
      ELSE bs*(relpages-otta::bigint + ipages-iotta::bigint) END
  END AS totalwastedbytes
FROM (
  SELECT
    nn.nspname AS schemaname,
    cc.relname AS tablename,
    COALESCE(cc.reltuples,0) AS reltuples,
    COALESCE(cc.relpages,0) AS relpages,
    COALESCE(bs,0) AS bs,
    COALESCE(CEIL((cc.reltuples*((datahdr+ma-
      (CASE WHEN datahdr%ma=0 THEN ma ELSE datahdr%ma END))+nullhdr2+4))/(bs-20::float)),0) AS otta,
    COALESCE(c2.relname,'?') AS iname, COALESCE(c2.reltuples,0) AS ituples, COALESCE(c2.relpages,0) AS ipages,
    COALESCE(CEIL((c2.reltuples*(datahdr-12))/(bs-20::float)),0) AS iotta -- very rough approximation, assumes all cols
  FROM
     pg_class cc
  JOIN pg_namespace nn ON cc.relnamespace = nn.oid AND nn.nspname <> 'information_schema'
  LEFT JOIN
  (
    SELECT
      ma,bs,foo.nspname,foo.relname,
      (datawidth+(hdr+ma-(case when hdr%ma=0 THEN ma ELSE hdr%ma END)))::numeric AS datahdr,
      (maxfracsum*(nullhdr+ma-(case when nullhdr%ma=0 THEN ma ELSE nullhdr%ma END))) AS nullhdr2
    FROM (
      SELECT
        ns.nspname, tbl.relname, hdr, ma, bs,
        SUM((1-coalesce(null_frac,0))*coalesce(avg_width, 2048)) AS datawidth,
        MAX(coalesce(null_frac,0)) AS maxfracsum,
        hdr+(
          SELECT 1+count(*)/8
          FROM pg_stats s2
          WHERE null_frac<>0 AND s2.schemaname = ns.nspname AND s2.tablename = tbl.relname
        ) AS nullhdr
      FROM pg_attribute att 
      JOIN pg_class tbl ON att.attrelid = tbl.oid
      JOIN pg_namespace ns ON ns.oid = tbl.relnamespace 
      LEFT JOIN pg_stats s ON s.schemaname=ns.nspname
      AND s.tablename = tbl.relname
      AND s.inherited=false
      AND s.attname=att.attname,
      (
        SELECT
          (SELECT current_setting('block_size')::numeric) AS bs,
            CASE WHEN SUBSTRING(SPLIT_PART(v, ' ', 2) FROM '#"[0-9]+.[0-9]+#"%' for '#')
              IN ('8.0','8.1','8.2') THEN 27 ELSE 23 END AS hdr,
          CASE WHEN v ~ 'mingw32' OR v ~ '64-bit' THEN 8 ELSE 4 END AS ma
        FROM (SELECT version() AS v) AS foo
      ) AS constants
      WHERE att.attnum > 0 AND tbl.relkind='r'
      GROUP BY 1,2,3,4,5
    ) AS foo
  ) AS rs
  ON cc.relname = rs.relname AND nn.nspname = rs.nspname
  LEFT JOIN pg_index i ON indrelid = cc.oid
  LEFT JOIN pg_class c2 ON c2.oid = i.indexrelid
) AS sml
};

    if (! defined $opt{include} and ! defined $opt{exclude}) {
        $SQL .= " WHERE sml.relpages - otta > $MINPAGES OR ipages - iotta > $MINIPAGES";
        $SQL .= " ORDER BY totalwastedbytes DESC LIMIT $LIMIT";
    }
    else {
        $SQL .= ' ORDER BY totalwastedbytes DESC';
    }

    ## Alternate versions for old versions
    my $SQL2 = $SQL;
    $SQL2 =~ s/AND s.inherited=false//; # 8.4 and earlier

    my $SQL3 = $SQL2;
    $SQL3 =~ s/SELECT current_setting.+?AS bs/(SELECT 8192) AS bs/; # 7.4 and earlier

    my $info = run_command($SQL, { version => [  "<8.0 $SQL3", "<9.0 $SQL2" ] } );

    if (defined $info->{db}[0] and exists $info->{db}[0]{error}) {
        ndie $info->{db}[0]{error};
    }

    my %seenit;

    ## Store the perf data for sorting at the end
    my %perf;

    $db = $info->{db}[0];

    if ($db->{slurp} !~ /\w+/o) {
        add_ok msg('bloat-nomin') unless $MRTG;
        return;
    }
    ## Not a 'regex' to run_command as we need to check the above first.
    if ($db->{slurp} !~ /\d+/) {
        add_unknown msg('invalid-query', $db->{slurp}) unless $MRTG;
        return;
    }

    my $max = -1;
    my $maxmsg = '?';

    ## The perf must be added before the add_x, so we defer the settings:
    my (@addwarn, @addcrit);

    for my $r (@{ $db->{slurp} }) {

        for my $v (values %$r) {
            $v =~ s/(\d+) bytes/pretty_size($1,1)/ge;
        }

        my ($dbname,$schema,$table,$tups,$pages,$otta,$bloat,$wp,$wb,$ws) = @$r{
            qw/ db schemaname tablename tups pages otta tbloat wastedpages wastedbytes wastedsize/};

        next if skip_item($table, $schema);

        my ($index,$irows,$ipages,$iotta,$ibloat,$iwp,$iwb,$iws) = @$r{
            qw/ iname irows ipages iotta ibloat wastedipgaes wastedibytes wastedisize/};

        ## Made it past the exclusions
        $max = -2 if $max == -1;

        ## Do the table first if we haven't seen it
        if (! $seenit{"$dbname.$schema.$table"}++) {
            my $nicename = perfname("$schema.$table");
            $perf{$wb}{$nicename}++;
            my $msg = msg('bloat-table', $dbname, $schema, $table, $tups, $pages, $otta, $bloat, $wb, $ws);
            my $ok = 1;
            my $perbloat = $bloat * 100;

            if ($MRTG) {
                $stats{table}{"DB=$dbname TABLE=$schema.$table"} = [$wb, $bloat];
                next;
            }
            if ($critical->($wb, $perbloat)) {
                push @addcrit => $msg;
                $ok = 0;
            }

            if ($ok and $warning->($wb, $perbloat)) {
                push @addwarn => $msg;
                $ok = 0;
            }
            ($max = $wb, $maxmsg = $msg) if $wb > $max and $ok;
        }

        ## Now the index, if it exists
        if ($index ne '?') {
            my $nicename = perfname($index);
            $perf{$iwb}{$nicename}++;
            my $msg = msg('bloat-index', $dbname, $index, $irows, $ipages, $iotta, $ibloat, $iwb, $iws);
            my $ok = 1;
            my $iperbloat = $ibloat * 100;

            if ($MRTG) {
                $stats{index}{"DB=$dbname INDEX=$index"} = [$iwb, $ibloat];
                next;
            }
            if ($critical->($iwb, $iperbloat)) {
                push @addcrit => $msg;
                $ok = 0;
            }

            if ($ok and $warning->($iwb, $iperbloat)) {
                push @addwarn => $msg;
                $ok = 0;
            }
            ($max = $iwb, $maxmsg = $msg) if $iwb > $max and $ok;
        }
    }

    ## Set a sorted limited perf
    $db->{perf} = '';
    my $count = 0;
  PERF: for my $size (sort {$b <=> $a } keys %perf) {
        for my $name (sort keys %{ $perf{$size} }) {
            $db->{perf} .= "$name=${size}B ";
            last PERF if $opt{perflimit} and ++$count >= $opt{perflimit};
        }
    }

    ## Now we can set the critical and warning
    for (@addcrit) {
        add_critical $_;
        $db->{perf} = '';
    }
    for (@addwarn) {
        add_warning $_;
        $db->{perf} = '';
    }

    if ($max == -1) {
        add_unknown msg('no-match-rel');
    }
    elsif ($max != -1) {
        add_ok $maxmsg;
    }

    if ($MRTG) {
        keys %stats or bad_mrtg(msg('unknown-error'));
        ## We are going to report the highest wasted bytes for table and index
        my ($one,$two,$msg) = ('','');
        ## Can also sort by ratio
        my $sortby = exists $opt{mrtg} and $opt{mrtg} eq 'ratio' ? 1 : 0;
        for (sort { $stats{table}{$b}->[$sortby] <=> $stats{table}{$a}->[$sortby] } keys %{$stats{table}}) {
            $one = $stats{table}{$_}->[$sortby];
            $msg = $_;
            last;
        }
        for (sort { $stats{index}{$b}->[$sortby] <=> $stats{index}{$a}->[$sortby] } keys %{$stats{index}}) {
            $two = $stats{index}{$_}->[$sortby];
            $msg .= " $_";
            last;
        }
        do_mrtg({one => $one, two => $two, msg => $msg});
    }

    return;

} ## end of check_bloat

sub check_checkpoint {

    ## Checks how long in seconds since the last checkpoint on a WAL slave

    ## Note that this value is actually the last checkpoint on the
    ## *master* (as copied from the WAL checkpoint record), so it more
    ## indicative that the master has been unable to complete a
    ## checkpoint for some other reason (i.e., unable to write dirty
    ## buffers or archive_command failure, etc).  As such, this check
    ## may make more sense on the master, or we may want to look at
    ## the WAL segments received/processed instead of the checkpoint
    ## timestamp.
    ## This check can use the optional --assume-standby-mode or
    ## --assume-prod: if the mode found is not the mode assumed, a
    ## CRITICAL is emitted.

    ## Supports: Nagios, MRTG
    ## Warning and critical are seconds
    ## Requires $ENV{PGDATA} or --datadir

    my ($warning, $critical) = validate_range
        ({
          type              => 'time',
          leastone          => 1,
          forcemrtg         => 1,
    });

    $db->{host} = '<none>';

    ## Run pg_controldata, grab the time
    $res = open_controldata();

    my $regex = msg('checkpoint-po');
    if ($res !~ /$regex\s*(.+)/) { ## no critic (ProhibitUnusedCapture)
        ## Just in case, check the English one as well
        $regex = msg_en('checkpoint-po');
        if ($res !~ /$regex\s*(.+)/) {
            ndie msg('checkpoint-noregex');
        }
    }
    my $last = $1;

    ## Convert to number of seconds
    eval {
        require Date::Parse;
        import Date::Parse;
    };
    if ($@) {
        ndie msg('checkpoint-nodp');
    }
    my $dt = str2time($last);
    if ($dt !~ /^\d+$/) {
        ndie msg('checkpoint-noparse', $last);
    }
    my $diff = time - $dt;
    my $msg = $diff==1 ? msg('checkpoint-ok') : msg('checkpoint-ok2', $diff);
    $db->{perf} = sprintf '%s=%s;%s;%s',
        perfname(msg('age')), $diff, $warning, $critical;

    my $mode = '';
    if ($STANDBY) {
        $mode = 'STANDBY';
    }
    if ($MASTER) {
        $mode = 'MASTER';
    }

    ## If we have an assume flag, then honor it.
    my $goodmode = 1;
    if ($opt{'assume-standby-mode'} and not $STANDBY) {
        $goodmode = 0;
        $mode = 'NOT STANDBY';
    }
    elsif ($opt{'assume-prod'} and not $MASTER) {
        $goodmode = 0;
        $mode = 'NOT MASTER';
    }

    if (length($mode) > 0) {
        $db->{perf} .= sprintf ' %s=%s',
            perfname(msg('mode')), $mode;
    }

    if ($MRTG) {
        do_mrtg({one => $diff, msg => $msg});
    }

    if ((length $critical and $diff >= $critical) or not $goodmode) {
        add_critical $msg;
        return;
    }

    if (length $warning and $diff >= $warning) {
        add_warning $msg;
        return;
    }

    add_ok $msg;

    return;

} ## end of check_checkpoint


sub check_cluster_id {


    ## Verify the Database System Identifier provided by pg_controldata
    ## Supports: Nagios, MRTG
    ## One of warning or critical must be given (but not both)
    ## It should run one time to find out the expected cluster-id
    ## You can use --critical="0" to find out the current cluster-id
    ## You can include or exclude settings as well
    ## Example:
    ##  check_postgres_cluster_id --critical="5633695740047915125"

    my ($warning, $critical) = validate_range({type => 'integer_string', onlyone => 1});

    $db->{host} = '<none>';

    ## Run pg_controldata, grab the cluster-id
    $res = open_controldata();

    my $regex = msg('checkcluster-id');
    if ($res !~ /$regex\s*(.+)/) { ## no critic (ProhibitUnusedCapture)
        ## Just in case, check the English one as well
        $regex = msg_en('checkcluster-id');
        if ($res !~ /$regex\s*(.+)/) {
            ndie msg('checkpoint-noregex');
        }
    }
    my $ident = $1;

    my $msg = msg('checkcluster-msg', $ident);
    if ($MRTG) {
        $opt{mrtg} or ndie msg('checksum-nomrtg');
        do_mrtg({one => $opt{mrtg} eq $ident ? 1 : 0, msg => $ident});
    }
    if ($critical and $critical ne $ident) {
        add_critical $msg;
    }
    elsif ($warning and $warning ne $ident) {
        add_warning $msg;
    }
    elsif (!$critical and !$warning) {
        add_unknown $msg;
    }
    else {
        add_ok $msg;
    }

    return;

} ## end of check_cluster_id


sub check_commitratio {

    ## Check the commitratio of one or more databases
    ## Supports: Nagios, MRTG
    ## mrtg reports the largest two databases
    ## By default, checks all databases
    ## Can check specific one(s) with include
    ## Can ignore some with exclude
    ## Warning and criticals are percentages
    ## Limit to a specific user (db owner) with the includeuser option
    ## Exclude users with the excludeuser option

    my ($warning, $critical) = validate_range({type => 'percent'});

    $SQL = qq{
SELECT
  round(100.*sd.xact_commit/(sd.xact_commit+sd.xact_rollback), 2) AS dcommitratio,
  d.datname,
  u.usename
FROM pg_stat_database sd
JOIN pg_database d ON (d.oid=sd.datid)
JOIN pg_user u ON (u.usesysid=d.datdba)
WHERE sd.xact_commit+sd.xact_rollback<>0
$USERWHERECLAUSE
};
    if ($opt{perflimit}) {
        $SQL .= " ORDER BY 1 DESC LIMIT $opt{perflimit}";
    }

    my $info = run_command($SQL, { regex => qr{\d+}, emptyok => 1, } );
    my $found = 0;

    for $db (@{$info->{db}}) {
        my $min = 101;
        $found = 1;
        my %s;
        for my $r (@{$db->{slurp}}) {

            next if skip_item($r->{datname});

            if ($r->{dcommitratio} <= $min) {
                $min = $r->{dcommitratio};
            }
            $s{$r->{datname}} = $r->{dcommitratio};
        }

        if ($MRTG) {
            do_mrtg({one => $min, msg => "DB: $db->{dbname}"});
        }
        if ($min > 100) {
            $stats{$db->{dbname}} = 0;
            if ($USERWHERECLAUSE) {
                add_ok msg('no-match-user');
            }
            else {
                add_unknown msg('no-match-db');
            }
            next;
        }

        my $msg = '';
        for (reverse sort {$s{$b} <=> $s{$a} or $a cmp $b } keys %s) {
            $msg .= "$_: $s{$_} ";
            $db->{perf} .= sprintf ' %s=%s;%s;%s',
                perfname($_), $s{$_}, $warning, $critical;
        }
        if (length $critical and $min <= $critical) {
            add_critical $msg;
        }
        elsif (length $warning and $min <= $warning) {
            add_warning $msg;
        }
        else {
            add_ok $msg;
        }
    }

    ## If no results, probably a version problem
    if (!$found and keys %unknown) {
        (my $first) = values %unknown;
        if ($first->[0][0] =~ /pg_database_size/) {
            ndie msg('dbsize-version');
        }
    }

    return;

} ## end of check_commitratio


sub check_connection {

    ## Check the connection, get the connection time and version
    ## No comparisons made: warning and critical are not allowed
    ## Suports: Nagios, MRTG

    if ($opt{warning} or $opt{critical}) {
        ndie msg('range-none');
    }

    my $info = run_command('SELECT version() AS v');

    for $db (@{$info->{db}}) {

        my $err = $db->{error} || '';
        if ($err =~ /FATAL|could not connect/) {
            $MRTG and do_mrtg({one => 0});
            add_critical $db->{error};
            return;
        }

        my $ver = ($db->{slurp}[0]{v} =~ /(\d+\.\d+\S+)/o) ? $1 : '';

        $MRTG and do_mrtg({one => $ver ? 1 : 0});

        if ($ver) {
            add_ok msg('version', $ver);
        }
        else {
            add_unknown msg('invalid-query', $db->{slurp}[0]{v});
        }
    }

    return;

} ## end of check_connection


sub check_custom_query {

    ## Run a user-supplied query, then parse the results
    ## If you end up using this to make a useful query, consider making it
    ## into a specific action and sending in a patch!
    ## valtype must be one of: string, time, size, integer

    my $valtype = $opt{valtype} || 'integer';

    my ($warning, $critical) = validate_range({type => $valtype, leastone => 1});

    my $query = $opt{query} or ndie msg('custom-nostring');

    my $reverse = $opt{reverse} || 0;

    my $info = run_command($query);

    for $db (@{$info->{db}}) {

        if (! @{$db->{slurp}}) {
            add_unknown msg('custom-norows');
            next;
        }

        my $goodrow = 0;

        ## The other column tells it the name to use as the perfdata value
        my $perfname;

        for my $r (@{$db->{slurp}}) {
            my $result = $r->{result};
            if (! defined $perfname) {
                $perfname = '';
                for my $name (keys %$r) {
                    next if $name eq 'result';
                    $perfname = $name;
                    last;
                }
            }
            $goodrow++;
            if ($perfname) {
                $db->{perf} .= sprintf ' %s=%s;%s;%s',
                    perfname($perfname), $r->{$perfname}, $warning, $critical;
            }
            my $gotmatch = 0;
            if (! defined $result) {
                add_unknown msg('custom-invalid');
                return;
            }
            if (length $critical) {
                if (($valtype eq 'string' and $reverse ? $result ne $critical : $result eq $critical)
                    or
                    ($valtype ne 'string' and $reverse ? $result <= $critical : $result >= $critical)) { ## covers integer, time, size
                    add_critical "$result";
                    $gotmatch = 1;
                }
            }

            if (length $warning and ! $gotmatch) {
                if (($valtype eq 'string' and $reverse ? $result ne $warning : $result eq $warning)
                    or
                    ($valtype ne 'string' and length $result and $reverse ? $result <= $warning : $result >= $warning)) {
                    add_warning "$result";
                    $gotmatch = 1;
                }
            }

            if (! $gotmatch) {
                add_ok "$result";
            }

        } ## end each row returned

        if (!$goodrow) {
            add_unknown msg('custom-invalid');
        }
    }

    return;

} ## end of check_custom_query


sub check_database_size {

    ## Check the size of one or more databases
    ## Supports: Nagios, MRTG
    ## mrtg reports the largest two databases
    ## By default, checks all databases
    ## Can check specific one(s) with include
    ## Can ignore some with exclude
    ## Warning and critical are bytes
    ## Valid units: b, k, m, g, t, e
    ## All above may be written as plural or with a trailing 'b'
    ## Limit to a specific user (db owner) with the includeuser option
    ## Exclude users with the excludeuser option

    my ($warning, $critical) = validate_range({type => 'size'});

    $USERWHERECLAUSE =~ s/AND/WHERE/;

    $SQL = qq{
SELECT pg_database_size(d.oid) AS dsize,
  pg_size_pretty(pg_database_size(d.oid)) AS pdsize,
  datname,
  usename
FROM pg_database d
LEFT JOIN pg_user u ON (u.usesysid=d.datdba)$USERWHERECLAUSE
};
    if ($opt{perflimit}) {
        $SQL .= " ORDER BY 1 DESC LIMIT $opt{perflimit}";
    }

    my $info = run_command($SQL, { regex => qr{\d+}, emptyok => 1, } );
    my $found = 0;

    for $db (@{$info->{db}}) {
        my $max = -1;
        $found = 1;
        my %s;
        for my $r (@{$db->{slurp}}) {

            next if skip_item($r->{datname});

            if ($r->{dsize} >= $max) {
                $max = $r->{dsize};
            }
            $s{$r->{datname}} = [$r->{dsize},$r->{pdsize}];
        }

        if ($MRTG) {
            do_mrtg({one => $max, msg => "DB: $db->{dbname}"});
        }
        if ($max < 0) {
            $stats{$db->{dbname}} = 0;
            if ($USERWHERECLAUSE) {
                add_ok msg('no-match-user');
            }
            else {
                add_unknown msg('no-match-db');
            }
            next;
        }

        my $msg = '';
        for (sort {$s{$b}[0] <=> $s{$a}[0] or $a cmp $b } keys %s) {
            $msg .= "$_: $s{$_}[0] ($s{$_}[1]) ";
            $db->{perf} .= sprintf ' %s=%s;%s;%s',
                perfname($_), $s{$_}[0], $warning, $critical;
        }
        if (length $critical and $max >= $critical) {
            add_critical $msg;
        }
        elsif (length $warning and $max >= $warning) {
            add_warning $msg;
        }
        else {
            add_ok $msg;
        }
    }

    ## If no results, probably a version problem
    if (!$found and keys %unknown) {
        (my $first) = values %unknown;
        if ($first->[0][0] =~ /pg_database_size/) {
            ndie msg('dbsize-version');
        }
    }

    return;

} ## end of check_database_size


sub check_dbstats {

    ## Returns values from the pg_stat_database view
    ## Supports: Cacti
    ## Assumes psql and target are the same version for the 8.3 check

    my ($warning, $critical) = validate_range
        ({
          type => 'cacti',
    });

    my $SQL = q{SELECT datname,
  numbackends AS backends,xact_commit AS commits,xact_rollback AS rollbacks,
  blks_read AS read, blks_hit AS hit};
    if ($opt{dbname}) {
        $SQL .= q{
 ,(SELECT SUM(idx_scan) FROM pg_stat_user_indexes) AS idxscan
 ,COALESCE((SELECT SUM(idx_tup_read) FROM pg_stat_user_indexes),0) AS idxtupread
 ,COALESCE((SELECT SUM(idx_tup_fetch) FROM pg_stat_user_indexes),0) AS idxtupfetch
 ,COALESCE((SELECT SUM(idx_blks_read) FROM pg_statio_user_indexes),0) AS idxblksread
 ,COALESCE((SELECT SUM(idx_blks_hit) FROM pg_statio_user_indexes),0) AS idxblkshit
 ,COALESCE((SELECT SUM(seq_scan) FROM pg_stat_user_tables),0) AS seqscan
 ,COALESCE((SELECT SUM(seq_tup_read) FROM pg_stat_user_tables),0) AS seqtupread
};
    }
    $SQL .= q{ FROM pg_stat_database};
    (my $SQL2 = $SQL) =~ s/AS seqtupread/AS seqtupread, tup_returned AS ret, tup_fetched AS fetch, tup_inserted AS ins, tup_updated AS upd, tup_deleted AS del/;

    my $info = run_command($SQL, {regex => qr{\w}, version => [ ">8.2 $SQL2" ] } );

    for $db (@{$info->{db}}) {
      ROW: for my $r (@{$db->{slurp}}) {

            my $dbname = $r->{datname};

            next ROW if skip_item($dbname);

            ## If dbnames were specififed, use those for filtering as well
            if (@{$opt{dbname}}) {
                my $keepit = 0;
                for my $drow (@{$opt{dbname}}) {
                    for my $d (split /,/ => $drow) {
                        $d eq $dbname and $keepit = 1;
                    }
                }
                next ROW unless $keepit;
            }

            my $msg = '';
            for my $col (qw/
backends commits rollbacks
read hit
idxscan idxtupread idxtupfetch idxblksread idxblkshit
seqscan seqtupread
ret fetch ins upd del/) {
                $msg .= "$col:";
                $msg .= (exists $r->{$col} and length $r->{$col}) ? $r->{$col} : 0;
                $msg .=  ' ';
            }
            print "${msg}dbname:$dbname\n";
        }
    }

    exit 0;

} ## end of check_dbstats


sub check_disabled_triggers {

    ## Checks how many disabled triggers are in the database
    ## Supports: Nagios, MRTG
    ## Warning and critical are integers, defaults to 1

    my ($warning, $critical) = validate_range
        ({
          type              => 'positive integer',
          default_warning   => 1,
          default_critical  => 1,
          forcemrtg         => 1,
    });

    $SQL = q{
SELECT tgrelid::regclass AS tname, tgname, tgenabled
FROM pg_trigger
WHERE tgenabled IS NOT TRUE ORDER BY tgname
};
    my $SQL83 = q{
SELECT tgrelid::regclass AS tname, tgname, tgenabled
FROM pg_trigger
WHERE tgenabled = 'D' ORDER BY tgname
};
    my $SQLOLD = q{SELECT 'FAIL' AS fail};

    my $info = run_command($SQL, { version => [ ">8.2 $SQL83", "<8.1 $SQLOLD" ] } );

    if (exists $info->{db}[0]{fail}) {
        ndie msg('die-action-version', $action, '8.1', $db->{version});
    }

    my $count = 0;
    my $dislis = '';
    for $db (@{$info->{db}}) {

      ROW: for my $r (@{$db->{slurp}}) {
            $count++;
            $dislis .= " $r->{tname}=>$r->{tgname}";
        }
        $MRTG and do_mrtg({one => $count});

        my $msg = msg('trigger-msg', "$count$dislis");

        if ($critical and $count >= $critical) {
            add_critical $msg;
        }
        elsif ($warning and $count >= $warning) {
            add_warning $msg;
        }
        else {
            add_ok $msg;
        }
    }

    return;

} ## end of check_disabled_triggers


sub check_disk_space {

    ## Check the available disk space used by postgres
    ## Supports: Nagios, MRTG
    ## Requires the executable "/bin/df"
    ## Must run as a superuser in the database (to examine 'data_directory' setting)
    ## Critical and warning are maximum size, or percentages
    ## Example: --critical="40 GB"
    ## NOTE: Needs to run on the same system (for now)
    ## XXX Allow custom ssh commands for remote df and the like

    my ($warning, $critical) = validate_size_or_percent_with_oper
        ({
          default_warning  => '90%',
          default_critical => '95%',
          });

    -x '/bin/df' or ndie msg('diskspace-nodf');

    ## Figure out where everything is.
    $SQL = q{
SELECT 'S' AS syn, name AS nn, setting AS val
FROM pg_settings
WHERE name = 'data_directory'
OR name ='log_directory'
UNION ALL
SELECT 'T' AS syn, spcname AS nn, spclocation AS val
FROM pg_tablespace
WHERE spclocation <> ''
};

    my $SQL92;
    ($SQL92 = $SQL) =~ s/spclocation/pg_tablespace_location(oid)/g;

    my $info = run_command($SQL, {version => [">9.1 $SQL92"]});

    my %dir; ## 1 = normal 2 = been checked -1 = does not exist
    my %seenfs;
    for $db (@{$info->{db}}) {
        my %i;
        for my $r (@{$db->{slurp}}) {
            $i{$r->{syn}}{$r->{nn}} = $r->{val};
        }
        if (! exists $i{S}{data_directory}) {
            add_unknown msg('diskspace-nodata');
            next;
        }
        my ($datadir,$logdir) = ($i{S}{data_directory},$i{S}{log_directory}||'');

        if (!exists $dir{$datadir}) {
            if (! -d $datadir) {
                add_unknown msg('diskspace-nodir', $datadir);
                $dir{$datadir} = -1;
                next;
            }
            $dir{$datadir} = 1;

            ## Check if the WAL files are on a separate disk
            my $xlog = "$datadir/pg_xlog";
            if (-l $xlog) {
                my $linkdir = readlink($xlog);
                $dir{$linkdir} = 1 if ! exists $dir{$linkdir};
            }
        }

        ## Check log_directory: relative or absolute
        if (length $logdir) {
            if ($logdir =~ /^\w/) { ## relative, check only if symlinked
                $logdir = "$datadir/$logdir";
                if (-l $logdir) {
                    my $linkdir = readlink($logdir);
                    $dir{$linkdir} = 1 if ! exists $dir{$linkdir};
                }
            }
            else { ## absolute, always check
                if ($logdir ne $datadir and ! exists $dir{$logdir}) {
                    $dir{$logdir} = 1;
                }
            }
        }

        ## Check all tablespaces
        for my $tsname (keys %{$i{T}}) {
            my $tsdir = $i{T}{$tsname};
            $dir{$tsdir} = 1 if ! exists $dir{$tsdir};
        }

        my $gotone = 0;
        for my $dir (keys %dir) {
            next if $dir{$dir} != 1;

            $dir{$dir} = 1;

            $COM = qq{/bin/df -kP "$dir" 2>&1};
            $res = qx{$COM};

            if ($res !~ /^.+\n(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\%\s+(\S+)/) {
                ndie msg('diskspace-fail', $COM, $res);
            }
            my ($fs,$total,$used,$avail,$percent,$mount) = ($1,$2*1024,$3*1024,$4*1024,$5,$6);

            ## If we've already done this one, skip it
            next if $seenfs{$fs}++;

            next if skip_item($fs);

            if ($MRTG) {
                $stats{$fs} = [$total,$used,$avail,$percent];
                next;
            }

            $gotone = 1;

            ## Rather than make another call with -h, do it ourselves
            my $prettyused = pretty_size($used);
            my $prettytotal = pretty_size($total);

            my $msg = msg('diskspace-msg', $fs, $mount, $prettyused, $prettytotal, $percent);

            $db->{perf} = sprintf '%s=%sB',
                perfname(msg('size')), $used;

            my $ok = 1;
            if ($critical->($used, $percent)) {
                add_critical $msg;
                $ok = 0;
            }

            if ($ok and $warning->($used, $percent)) {
                add_warning $msg;
                $ok = 0;
            }

            if ($ok) {
                add_ok $msg;
            }
        } ## end each dir

        next if $MRTG;

        if (!$gotone) {
            add_unknown msg('no-match-fs');
        }
    }

    if ($MRTG) {
        keys %stats or bad_mrtg(msg('unknown-error'));
        ## Get the highest by total size or percent (total, used, avail, percent)
        ## We default to 'available'
        my $sortby = exists $opt{mrtg}
            ? $opt{mrtg} eq 'total'   ? 0
            : $opt{mrtg} eq 'used'    ? 1
            : $opt{mrtg} eq 'avail'   ? 2
            : $opt{mrtg} eq 'percent' ? 3 : 2 : 2;
        my ($one,$two,$msg) = ('','','');
        for (sort { $stats{$b}->[$sortby] <=> $stats{$a}->[$sortby] } keys %stats) {
            if ($one eq '') {
                $one = $stats{$_}->[$sortby];
                $msg = $_;
                next;
            }
            $two = $stats{$_}->[$sortby];
            last;
        }
        do_mrtg({one => $one, two => $two, msg => $msg});
    }

    return;

} ## end of check_disk_space


sub check_fsm_pages {

    ## Check on the percentage of free space map pages in use
    ## Supports: Nagios, MRTG
    ## Must run as superuser
    ## Requires pg_freespacemap contrib module
    ## Critical and warning are a percentage of max_fsm_pages
    ## Example: --critical=95

    my ($warning, $critical) = validate_range
        ({
          type              => 'percent',
          default_warning   => '85%',
          default_critical  => '95%',
          });

    (my $w = $warning) =~ s/\D//;
    (my $c = $critical) =~ s/\D//;
    my $SQL = q{
SELECT pages, maxx, ROUND(100*(pages/maxx)) AS percent
FROM 
  (SELECT (sumrequests+numrels)*chunkpages AS pages
   FROM (SELECT SUM(CASE WHEN avgrequest IS NULL 
     THEN interestingpages/32 ELSE interestingpages/16 END) AS sumrequests,
     COUNT(relfilenode) AS numrels, 16 AS chunkpages FROM pg_freespacemap_relations) AS foo) AS foo2,
  (SELECT setting::NUMERIC AS maxx FROM pg_settings WHERE name = 'max_fsm_pages') AS foo3
};
    my $SQLNOOP = q{SELECT 'FAIL' AS fail};

    my $info = run_command($SQL, { version => [ ">8.3 $SQLNOOP" ] } );

    if (exists $info->{db}[0]{slurp}[0]{fail}) {
        add_unknown msg('fsm-page-highver');
        return;
    }

    for $db (@{$info->{db}}) {
        for my $r (@{$db->{slurp}}) {
            my ($pages,$max,$percent) = ($r->{pages}||0,$r->{maxx},$r->{percent}||0);

            $MRTG and do_mrtg({one => $percent, two => $pages});

            my $msg = msg('fsm-page-msg', $pages, $max, $percent);

            if (length $critical and $percent >= $c) {
                add_critical $msg;
            }
            elsif (length $warning and $percent >= $w) {
                add_warning $msg;
            }
            else {
                add_ok $msg;
            }
        }
    }

    return;

} ## end of check_fsm_pages


sub check_fsm_relations {

    ## Check on the % of free space map relations in use
    ## Supports: Nagios, MRTG
    ## Must run as superuser
    ## Requires pg_freespacemap contrib module
    ## Critical and warning are a percentage of max_fsm_relations
    ## Example: --critical=95

    my ($warning, $critical) = validate_range
        ({
          type              => 'percent',
          default_warning   => '85%',
          default_critical  => '95%',
          });

    (my $w = $warning) =~ s/\D//;
    (my $c = $critical) =~ s/\D//;

    my $SQL = q{
SELECT maxx, cur, ROUND(100*(cur/maxx)) AS percent
FROM (SELECT 
    (SELECT COUNT(*) FROM pg_freespacemap_relations) AS cur,
    (SELECT setting::NUMERIC FROM pg_settings WHERE name='max_fsm_relations') AS maxx) x
};
    my $SQLNOOP = q{SELECT 'FAIL' AS fail};

    my $info = run_command($SQL, { version => [ ">8.3 $SQLNOOP" ] } );

    if (exists $info->{db}[0]{slurp}[0]{fail}) {
        add_unknown msg('fsm-rel-highver');
        return;
    }

    for $db (@{$info->{db}}) {

        for my $r (@{$db->{slurp}}) {
            my ($max,$cur,$percent) = ($r->{maxx},$r->{cur},$r->{percent}||0);

            $MRTG and do_mrtg({one => $percent, two => $cur});

            my $msg = msg('fsm-rel-msg', $cur, $max, $percent);

            if (length $critical and $percent >= $c) {
                add_critical $msg;
            }
            elsif (length $warning and $percent >= $w) {
                add_warning $msg;
            }
            else {
                add_ok $msg;
            }
        }

    }

    return;

} ## end of check_fsm_relations


sub check_hitratio {

    ## Check the hitratio of one or more databases
    ## Supports: Nagios, MRTG
    ## mrtg reports the largest two databases
    ## By default, checks all databases
    ## Can check specific one(s) with include
    ## Can ignore some with exclude
    ## Warning and criticals are percentages
    ## Limit to a specific user (db owner) with the includeuser option
    ## Exclude users with the excludeuser option

    my ($warning, $critical) = validate_range({type => 'percent'});

    $SQL = qq{
SELECT
  round(100.*sd.blks_hit/(sd.blks_read+sd.blks_hit), 2) AS dhitratio,
  d.datname,
  u.usename
FROM pg_stat_database sd
JOIN pg_database d ON (d.oid=sd.datid)
JOIN pg_user u ON (u.usesysid=d.datdba)
WHERE sd.blks_read+sd.blks_hit<>0
$USERWHERECLAUSE
};
    if ($opt{perflimit}) {
        $SQL .= " ORDER BY 1 DESC LIMIT $opt{perflimit}";
    }

    my $info = run_command($SQL, { regex => qr{\d+}, emptyok => 1, } );
    my $found = 0;

    for $db (@{$info->{db}}) {
        my $min = 101;
        $found = 1;
        my %s;
        for my $r (@{$db->{slurp}}) {

            next if skip_item($r->{datname});

            if ($r->{dhitratio} <= $min) {
                $min = $r->{dhitratio};
            }
            $s{$r->{datname}} = $r->{dhitratio};
        }

        if ($MRTG) {
            do_mrtg({one => $min, msg => "DB: $db->{dbname}"});
        }
        if ($min > 100) {
            $stats{$db->{dbname}} = 0;
            if ($USERWHERECLAUSE) {
                add_ok msg('no-match-user');
            }
            else {
                add_unknown msg('no-match-db');
            }
            next;
        }

        my $msg = '';
        for (reverse sort {$s{$b} <=> $s{$a} or $a cmp $b } keys %s) {
            $msg .= "$_: $s{$_} ";
            $db->{perf} .= sprintf ' %s=%s;%s;%s',
                perfname($_), $s{$_}, $warning, $critical;
        }
        if (length $critical and $min <= $critical) {
            add_critical $msg;
        }
        elsif (length $warning and $min <= $warning) {
            add_warning $msg;
        }
        else {
            add_ok $msg;
        }
    }

    ## If no results, probably a version problem
    if (!$found and keys %unknown) {
        (my $first) = values %unknown;
        if ($first->[0][0] =~ /pg_database_size/) {
            ndie msg('dbsize-version');
        }
    }

    return;

} ## end of check_hitratio


sub check_hot_standby_delay {

    ## Check on the delay in PITR replication between master and slave
    ## Supports: Nagios, MRTG
    ## Critical and warning are the delay between master and slave xlog locations
    ## and/or transaction timestamps.  If both are specified, both are checked.
    ## Examples:
    ## --critical=1024
    ## --warning=5min
    ## --warning='1048576 and 2min' --critical='16777216 and 10min'

    my ($warning, $wtime, $critical, $ctime) = validate_integer_for_time({default_to_int => 1});
    if ($psql_version < 9.1 and (length $wtime or length $ctime)) { # FIXME: check server version instead
        add_unknown msg('hs-time-version');
        return;
    }

    # check if master and slave comply with the check using pg_is_in_recovery()
    my ($master, $slave);
    $SQL = q{SELECT pg_is_in_recovery() AS recovery;};

    # Check if master is online (e.g. really a master)
    for my $x (1..2) {
        my $info = run_command($SQL, { dbnumber => $x, regex => qr([tf]) });

        for $db (@{$info->{db}}) {
            my $status = $db->{slurp}[0];
            if ($status->{recovery} eq 't') {
                $slave = $x;
                last;
            }
            if ($status->{recovery} eq 'f') {
                $master = $x;
                last;
            }
        }
    }
    if (! defined $slave and ! defined $master) {
        add_unknown msg('hs-no-role');
        return;
    }

    ## If no slave detected, assume it is 2
    if (! defined $slave) {
        $slave = 2;
    }

    ## Get xlog positions
    my ($moffset, $s_rec_offset, $s_rep_offset, $time_delta);

    ## On slave
    $SQL = q{SELECT pg_last_xlog_receive_location() AS receive, pg_last_xlog_replay_location() AS replay};
    if ($psql_version >= 9.1) {
        $SQL .= q{, COALESCE(ROUND(EXTRACT(epoch FROM now() - pg_last_xact_replay_timestamp())),0) AS seconds};
    }
    my $info = run_command($SQL, { dbnumber => $slave, regex => qr/\// });
    my $saved_db;
    for $db (@{$info->{db}}) {
        my $receive = $db->{slurp}[0]{receive};
        my $replay = $db->{slurp}[0]{replay};
        $time_delta = $db->{slurp}[0]{seconds};

        if (defined $receive) {
            my ($a, $b) = split(/\//, $receive);
            $s_rec_offset = (hex('ff000000') * hex($a)) + hex($b);
        }

        if (defined $replay) {
            my ($a, $b) = split(/\//, $replay);
            $s_rep_offset = (hex('ff000000') * hex($a)) + hex($b);
        }

        $saved_db = $db if ! defined $saved_db;
    }

    if (! defined $s_rec_offset and ! defined $s_rep_offset) {
        add_unknown msg('hs-no-location', 'slave');
        return;
    }

    ## On master
    $SQL = q{SELECT pg_current_xlog_location() AS location};
    $info = run_command($SQL, { dbnumber => $master });
    for $db (@{$info->{db}}) {
        my $location = $db->{slurp}[0]{location};
        next if ! defined $location;

        my ($x, $y) = split(/\//, $location);
        $moffset = (hex('ff000000') * hex($x)) + hex($y);
        $saved_db = $db if ! defined $saved_db;
    }

    if (! defined $moffset) {
        add_unknown msg('hs-no-location', 'master');
        return;
    }

    ## Compute deltas
    $db = $saved_db;
    my $rec_delta = $moffset - $s_rec_offset;
    my $rep_delta = $moffset - $s_rep_offset;

    # Make sure it's always positive or zero
    $rec_delta = 0 if $rec_delta < 0;
    $rep_delta = 0 if $rep_delta < 0;
    if (defined $time_delta and $time_delta < 0) {
        add_unknown msg('hs-future-replica');
        return;
    }

    $MRTG and do_mrtg($psql_version >= 9.1 ?
        {one => $rep_delta, two => $rec_delta, three => $time_delta} :
        {one => $rep_delta, two => $rec_delta});

    $db->{perf} = sprintf ' %s=%s;%s;%s ',
        perfname(msg('hs-replay-delay')), $rep_delta, $warning, $critical;
    $db->{perf} .= sprintf ' %s=%s;%s;%s',
        perfname(msg('hs-receive-delay')), $rec_delta, $warning, $critical;
    if ($psql_version >= 9.1) {
        $db->{perf} .= sprintf ' %s=%s;%s;%s',
            perfname(msg('hs-time-delay')), $time_delta, $wtime, $ctime;
    }

    ## Do the check on replay delay in case SR has disconnected because it way too far behind
    my $msg = qq{$rep_delta};
    if ($psql_version >= 9.1) {
        $msg .= qq{ and $time_delta seconds}
    }
    if ((length $critical or length $ctime) and (!length $critical or length $critical and $rep_delta > $critical) and (!length $ctime or length $ctime and $time_delta > $ctime)) {
        add_critical $msg;
    }
    elsif ((length $warning or length $wtime) and (!length $warning or length $warning and $rep_delta > $warning) and (!length $wtime or length $wtime and $time_delta > $wtime)) {
        add_warning $msg;
    }
    else {
        add_ok $msg;
    }

    return;

} ## end of check_hot_standby_delay


sub check_last_analyze {
    my $auto = shift || '';
    return check_last_vacuum_analyze('analyze', $auto);
}


sub check_last_vacuum {
    my $auto = shift || '';
    return check_last_vacuum_analyze('vacuum', $auto);
}


sub check_last_vacuum_analyze {

    my $type = shift || 'vacuum';
    my $auto = shift || 0;

    ## Check the last time things were vacuumed or analyzed
    ## Supports: Nagios, MRTG
    ## NOTE: stats_row_level must be set to on in your database (if version 8.2)
    ## By default, reports on the oldest value in the database
    ## Can exclude and include tables
    ## Warning and critical are times, default to seconds
    ## Valid units: s[econd], m[inute], h[our], d[ay]
    ## All above may be written as plural as well (e.g. "2 hours")
    ## Limit to a specific user (relation owner) with the includeuser option
    ## Exclude users with the excludeuser option
    ## Example:
    ## --exclude=~pg_ --include=pg_class,pg_attribute

    my ($warning, $critical) = validate_range
        ({
         type              => 'time',
          default_warning  => '1 day',
          default_critical => '2 days',
          });

    my $criteria = $auto ?
        qq{pg_stat_get_last_auto${type}_time(c.oid)}
            : qq{GREATEST(pg_stat_get_last_${type}_time(c.oid), pg_stat_get_last_auto${type}_time(c.oid))};

    ## Do include/exclude earlier for large pg_classes?
    $SQL = qq{
SELECT current_database() AS datname, nspname AS sname, relname AS tname,
  CASE WHEN v IS NULL THEN -1 ELSE round(extract(epoch FROM now()-v)) END AS ltime,
  CASE WHEN v IS NULL THEN '?' ELSE TO_CHAR(v, '$SHOWTIME') END AS ptime
FROM (SELECT nspname, relname, $criteria AS v
      FROM pg_class c, pg_namespace n
      WHERE relkind = 'r'
      AND n.oid = c.relnamespace
      AND n.nspname <> 'information_schema'
      ORDER BY 3) AS foo
};
    if ($opt{perflimit}) {
        $SQL .= ' ORDER BY 4 DESC';
    }

    if ($USERWHERECLAUSE) {
        $SQL =~ s/ WHERE/, pg_user u WHERE u.usesysid=c.relowner$USERWHERECLAUSE AND/;
    }

    my $info = run_command($SQL, { regex => qr{\w}, emptyok => 1 } );

    for $db (@{$info->{db}}) {

        if (! @{$db->{slurp}} and $USERWHERECLAUSE) {
            $stats{$db->{dbname}} = 0;
            add_ok msg('no-match-user');
            return;
        }

        ## -1 means no tables found at all
        ## -2 means exclusion rules took effect
        ## -3 means no tables were ever vacuumed/analyzed
        my $maxtime = -1;
        my $maxptime = '?';
        my ($minrel,$maxrel) = ('?','?'); ## no critic
        my $mintime = 0; ## used for MRTG only
        my $count = 0;
        my $found = 0;
      ROW: for my $r (@{$db->{slurp}}) {
            my ($dbname,$schema,$name,$time,$ptime) = @$r{qw/ datname sname tname ltime ptime/};
            if (skip_item($name, $schema)) {
                $maxtime = -2 if $maxtime < 1;
                next ROW;
            }
            $found++;
            if ($time >= 0) {
                $db->{perf} .= sprintf ' %s=%ss;%s;%s',
                    perfname("$dbname.$schema.$name"),$time, $warning, $critical;
            }
            if ($time > $maxtime) {
                $maxtime = $time;
                $maxrel = "DB: $dbname TABLE: $schema.$name";
                $maxptime = $ptime;
            }
            if ($time > 0 and ($time < $mintime or !$mintime)) {
                $mintime = $time;
                $minrel = "DB: $dbname TABLE: $schema.$name";
            }
            if ($opt{perflimit}) {
                last if ++$count >= $opt{perflimit};
            }
        }
        if ($MRTG) {
            $maxrel eq '?' and $maxrel = "DB: $db->{dbname} TABLE: ?";
            do_mrtg({one => $mintime, msg => $maxrel});
            return;
        }
        if ($maxtime == -2) {
            add_unknown (
                $found ? $type eq 'vacuum' ? msg('vac-nomatch-v')
                : msg('vac-nomatch-a')
                : msg('no-match-table') ## no critic (RequireTrailingCommaAtNewline)
            );
        }
        elsif ($maxtime < 0) {
            add_unknown $type eq 'vacuum' ? msg('vac-nomatch-v') : msg('vac-nomatch-a');
        }
        else {
            my $showtime = pretty_time($maxtime, 'S');
            my $msg = "$maxrel: $maxptime ($showtime)";
            if ($critical and $maxtime >= $critical) {
                add_critical $msg;
            }
            elsif ($warning and $maxtime >= $warning) {
                add_warning $msg;
            }
            else {
                add_ok $msg;
            }
        }
    }

    return;

} ## end of check_last_vacuum_analyze


sub check_listener {

    ## Check for a specific listener
    ## Supports: Nagios, MRTG
    ## Critical and warning are simple strings, or regex if starts with a ~
    ## Example: --critical="~bucardo"

    if ($MRTG and exists $opt{mrtg}) {
        $opt{critical} = $opt{mrtg};
    }

    my ($warning, $critical) = validate_range({type => 'restringex', forcemrtg => 1});

    my $string = length $critical ? $critical : $warning;
    my $regex = ($string =~ s/^~//) ? '~' : '=';

    $SQL = "SELECT count(*) AS c FROM pg_listener WHERE relname $regex '$string'";
    my $info = run_command($SQL);

    for $db (@{$info->{db}}) {
        if ($db->{slurp}[0]{c} !~ /(\d+)/) {
            add_unknown msg('invalid-query', $db->{slurp});
            next;
        }
        my $count = $1;
        if ($MRTG) {
            do_mrtg({one => $count});
        }
        $db->{perf} .= sprintf '%s=%s',
            perfname(msg('listening')), $count;
        my $msg = msg('listener-msg', $count);
        if ($count >= 1) {
            add_ok $msg;
        }
        elsif ($critical) {
            add_critical $msg;
        }
        else {
            add_warning $msg;
        }
    }
    return;

} ## end of check_listener


sub check_locks {

    ## Check the number of locks
    ## Supports: Nagios, MRTG
    ## By default, checks all databases
    ## Can check specific databases with include
    ## Can ignore databases with exclude
    ## Warning and critical are either simple numbers, or more complex:
    ## Use locktype=number:locktype2=number
    ## The locktype can be "total", "waiting", or the name of a lock
    ## Lock names are case-insensitive, and do not need the "lock" at the end.
    ## Example: --warning=100 --critical="total=200;exclusive=20;waiting=5"

    my ($warning, $critical) = validate_range
        ({
          type             => 'multival',
          default_warning  => 100,
          default_critical => 150,
          });

    $SQL = q{SELECT granted, mode, datname FROM pg_locks l RIGHT JOIN pg_database d ON (d.oid=l.database) WHERE d.datallowconn};
    my $info = run_command($SQL, { regex => qr[\s*\w+\s*\|\s*] });

    # Locks are counted globally not by db.
    # We output for each db, following the specific warning and critical :
    # time=00.1 foodb.exclusive=2;;3 foodb.total=10;;30 postgres.exclusive=0;;3 postgres.total=1;;3
    for $db (@{$info->{db}}) {
        my $gotone = 0;
        my %dblock;
        my %totallock = (total => 0);
      ROW: for my $r (@{$db->{slurp}}) {
            my ($granted,$mode,$dbname) = ($r->{granted}, lc $r->{mode}, $r->{datname});

            ## May be forcibly skipping this database via arguments
            next ROW if skip_item($dbname);

            ## If we hit the right join, simply make an empty total entry
            if (! length $granted) {
                $dblock{$dbname}{total} ||= 0;
            }
            else {
                $dblock{$dbname}{total}++;
                $gotone = 1;
                $mode =~ s{lock$}{};
                $dblock{$dbname}{$mode}++;
                $dblock{$dbname}{waiting}++ if $granted ne 't';
            }
        }

        # Compute total, add hash key for critical and warning specific check
        for my $k (keys %dblock) {

            if ($warning) {
                for my $l (keys %{$warning}) {
                    $dblock{$k}{$l} = 0 if ! exists $dblock{$k}{$l};
                }
            }
            if ($critical) {
                for my $l (keys %{$critical}) {
                    #$dblock{$k}{$l} = 0 if ! exists $dblock{$k}{$l};
                }
            }
            for my $m (keys %{$dblock{$k}}){
                $totallock{$m} += $dblock{$k}{$m};
            }
        }

        if ($MRTG) {
            do_mrtg( {one => $totallock{total}, msg => "DB: $db->{dbname}" } );
        }

        # Nagios perfdata output
        for my $dbname (sort keys %dblock) {
            for my $type (sort keys %{ $dblock{$dbname} }) {
                next if ((! $critical or ! exists $critical->{$type})
                             and (!$warning or ! exists $warning->{$type}));
                $db->{perf} .= sprintf ' %s=%s;',
                    perfname("$dbname.$type"), $dblock{$dbname}{$type};
                if ($warning and exists $warning->{$type}) {
                    $db->{perf} .= $warning->{$type};
                }
                if ($critical and $critical->{$type}) {
                    $db->{perf} .= ";$critical->{$type}";
                }
            }
        }

        if (!$gotone) {
            add_unknown msg('no-match-db');
            next;
        }

        ## If not specific errors, just use the total
        my $ok = 1;
        for my $type (sort keys %totallock) {
            if ($critical and exists $critical->{$type} and $totallock{$type} >= $critical->{$type}) {
                ($type eq 'total')
                    ? add_critical msg('locks-msg2', $totallock{total})
                    : add_critical msg('locks-msg', $type, $totallock{$type});
                $ok = 0;
            }
            if ($warning and exists $warning->{$type} and $totallock{$type} >= $warning->{$type}) {
                ($type eq 'total')
                ? add_warning msg('locks-msg2', $totallock{total})
                : add_warning msg('locks-msg', $type, $totallock{$type});
                $ok = 0;
            }
        }
        if ($ok) {
            my %show;
            if (!keys %critical and !keys %warning) {
                $show{total} = 1;
            }
            for my $type (keys %critical) {
                $show{$type} = 1;
            }
            for my $type (keys %warning) {
                $show{$type} = 1;
            }
            my $msg = '';
            for (sort keys %show) {
                $msg .= sprintf "$_=%d ", $totallock{$_} || 0;
            }
            add_ok $msg;
        }
    }

    return;

} ## end of check_locks


sub check_logfile {

    ## Make sure the logfile is getting written to
    ## Supports: Nagios, MRTG
    ## Especially useful for syslog redirectors
    ## Should be run on the system housing the logs
    ## Optional argument "logfile" tells where the logfile is
    ## Allows for some conversion characters.
    ## Example: --logfile="/syslog/%Y-m%-d%/H%/postgres.log"
    ## Critical and warning are not used: it's either ok or critical.

    my $critwarn = $opt{warning} ? 0 : 1;

    $SQL = q{
SELECT name, CASE WHEN length(setting)<1 THEN '?' ELSE setting END AS s
FROM pg_settings
WHERE name IN ('log_destination','log_directory','log_filename','redirect_stderr','syslog_facility')
ORDER BY name
};

    my $logfilere = qr{^[\w_\s\/%\-\.]+$};
    if (exists $opt{logfile} and $opt{logfile} !~ $logfilere) {
        ndie msg('logfile-opt-bad');
    }

    my $info = run_command($SQL);
    $VERBOSE >= 3 and warn Dumper $info;

    for $db (@{$info->{db}}) {
        my $i;
        for my $r (@{$db->{slurp}}) {
            $i->{$r->{name}} = $r->{s} || '?';
        }
        for my $word (qw{ log_destination log_directory log_filename redirect_stderr syslog_facility }) {
            $i->{$word} = '?' if ! exists $i->{$word};
        }

        ## Figure out what we think the log file will be
        my $logfile ='';
        if (exists $opt{logfile} and $opt{logfile} =~ /\w/) {
            $logfile = $opt{logfile};
        }
        else {
            if ($i->{log_destination} eq 'syslog') {
                ## We'll make a best effort to figure out where it is. Using the --logfile option is preferred.
                $logfile = '/var/log/messages';
                if (open my $cfh, '<', '/etc/syslog.conf') {
                    while (<$cfh>) {
                        if (/\b$i->{syslog_facility}\.(?!none).+?([\w\/]+)$/i) {
                            $logfile = $1;
                        }
                    }
                }
                if (!$logfile or ! -e $logfile) {
                    ndie msg('logfile-syslog', $i->{syslog_facility});
                }
            }
            elsif ($i->{log_destination} eq 'stderr') {
                if ($i->{redirect_stderr} ne 'yes') {
                    ndie msg('logfile-stderr');
                }
            }
        }

        ## We now have a logfile (or a template)..parse it into pieces.
        ## We need at least hour, day, month, year
        my @t = localtime;
        my ($H,$d,$m,$Y) = (sprintf ('%02d',$t[2]),sprintf('%02d',$t[3]),sprintf('%02d',$t[4]+1),$t[5]+1900);
        my $y = substr($Y,2,4);
        if ($logfile !~ $logfilere) {
            ndie msg('logfile-bad',$logfile);
        }
        $logfile =~ s/%%/~~/g;
        $logfile =~ s/%Y/$Y/g;
        $logfile =~ s/%y/$y/g;
        $logfile =~ s/%m/$m/g;
        $logfile =~ s/%d/$d/g;
        $logfile =~ s/%H/$H/g;

        $VERBOSE >= 3 and warn msg('logfile-debug', $logfile);

        if (! -e $logfile) {
            my $msg = msg('logfile-dne', $logfile);
            $MRTG and ndie $msg;
            if ($critwarn) {
                add_unknown $msg;
            }
            else {
                add_warning $msg;
            }
            next;
        }
        my $logfh;
        unless (open $logfh, '<', $logfile) {
            add_unknown msg('logfile-openfail', $logfile, $!);
            next;
        }
        seek($logfh, 0, 2) or ndie msg('logfile-seekfail', $logfile, $!);

        ## Throw a custom error string.
        ## We do the number first as old versions only show part of the string.
        my $random_number = int rand(999999999999);
        my $funky = sprintf "check_postgres_logfile_error_$random_number $ME DB=$db->{dbname} PID=$$ Time=%s",
            scalar localtime;

        ## Cause an error on just this target
        delete @{$db}{qw(ok slurp totaltime)};
        my $badinfo = run_command("$funky", {failok => 1, target => $db} );

        my $MAXSLEEPTIME = $opt{timeout} || 20;
        my $SLEEP = 1;
        my $found = 0;
        LOGWAIT: {
            sleep $SLEEP;
            seek $logfh, 0, 1 or ndie msg('logfile-seekfail', $logfile, $!);
            while (<$logfh>) {
                if (/logfile_error_$random_number/) { ## Some logs break things up, so we don't use funky
                    $found = 1;
                    last LOGWAIT;
                }
            }
            $MAXSLEEPTIME -= $SLEEP;
            redo if $MAXSLEEPTIME > 0;
            my $msg = msg('logfile-fail', $logfile);
            $MRTG and do_mrtg({one => 0, msg => $msg});
            if ($critwarn) {
                add_critical $msg;
            }
            else {
                add_warning $msg;
            }
        }
        close $logfh or ndie msg('file-noclose', $logfile, $!);

        if ($found == 1) {
            $MRTG and do_mrtg({one => 1});
            add_ok msg('logfile-ok', $logfile);
        }
    }
    return;

} ## end of check_logfile


sub find_new_version {

    ## Check for newer versions of some program

    my $program = shift or die;
    my $exec = shift or die;
    my $url = shift or die;

    ## The format is X.Y.Z [optional message]
    my $versionre = qr{((\d+)\.(\d+)\.(\d+))\s*(.*)};
    my ($cversion,$cmajor,$cminor,$crevision,$cmessage) = ('','','','','');
    my $found = 0;

    ## Try to fetch the current version from the web
    for my $meth (@get_methods) {
        eval {
            my $COM = "$meth $url";
            $VERBOSE >= 1 and warn "TRYING: $COM\n";
            my $info = qx{$COM 2>/dev/null};
            ## Postgres is slightly different
            if ($program eq 'Postgres') {
                $cmajor = {};
                while ($info =~ /<title>(\d+)\.(\d+)\.(\d+)/g) {
                    $found = 1;
                    $cmajor->{"$1.$2"} = $3;
                }
            }
            elsif ($info =~ $versionre) {
                $found = 1;
                ($cversion,$cmajor,$cminor,$crevision,$cmessage) = ($1, int $2, int $3, int $4, $5);
                if ($VERBOSE >= 1) {
                    $info =~ s/\s+$//s;
                    warn "Remote version string: $info\n";
                    warn "Remote version: $cversion\n";
                }
            }
        };
        last if $found;
    }

    if (! $found) {
        add_unknown msg('new-ver-nocver', $program);
        return;
    }

    ## Figure out the local copy's version
    my $output;
    eval {
        ## We may already know the version (e.g. ourselves)
        $output = ($exec =~ /\d+\.\d+/) ? $exec : qx{$exec --version 2>&1};
    };
    if ($@ or !$output) {
        if ($program eq 'tail_n_mail') {
            ## Check for the old name
            eval {
                $output = qx{tail_n_mail.pl --version 2>&1};
            };
        }
        if ($@ or !$output) {
            add_unknown msg('new-ver-badver', $program);
            return;
        }
    }

    if ($output !~ $versionre) {
        add_unknown msg('new-ver-nolver', $program);
        return;
    }
    my ($lversion,$lmajor,$lminor,$lrevision) = ($1, int $2, int $3, int $4);
    if ($VERBOSE >= 1) {
        $output =~ s/\s+$//s;
        warn "Local version string: $output\n";
        warn "Local version: $lversion\n";
    }

    ## Postgres is a special case
    if ($program eq 'Postgres') {
        my $lver = "$lmajor.$lminor";
        if (! exists $cmajor->{$lver}) {
            add_unknown msg('new-ver-nocver', $program);
            return;
        }
        $crevision = $cmajor->{$lver};
        $cmajor = $lmajor;
        $cminor = $lminor;
        $cversion = "$cmajor.$cminor.$crevision";
    }

    ## Most common case: everything matches
    if ($lversion eq $cversion) {
        add_ok msg('new-ver-ok', $lversion, $program);
        return;
    }

    ## Check for a revision update
    if ($lmajor==$cmajor and $lminor==$cminor and $lrevision<$crevision) {
        add_critical msg('new-ver-warn', $cversion, $program, $lversion);
        return;
    }

    ## Check for a major update
    if ($lmajor<$cmajor or ($lmajor==$cmajor and $lminor<$cminor)) {
        add_warning msg('new-ver-warn', $cversion, $program, $lversion);
        return;
    }

    ## Anything else must be time travel, which we cannot handle
    add_unknown msg('new-ver-tt', $program, $lversion, $cversion);
    return;

} ## end of find_new_version


sub check_new_version_bc {

    ## Check if a newer version of Bucardo is available

    my $url = 'http://bucardo.org/bucardo/latest_version.txt';
    find_new_version('Bucardo', 'bucardo_ctl', $url);

    return;

} ## end of check_new_version_bc


sub check_new_version_box {

    ## Check if a newer version of boxinfo is available

    my $url = 'http://bucardo.org/boxinfo/latest_version.txt';
    find_new_version('boxinfo', 'boxinfo.pl', $url);

    return;

} ## end of check_new_version_box


sub check_new_version_cp {

    ## Check if a new version of check_postgres.pl is available

    my $url = 'http://bucardo.org/check_postgres/latest_version.txt';
    find_new_version('check_postgres', $VERSION, $url);

    return;

} ## end of check_new_version_cp


sub check_new_version_pg {

    ## Check if a new version of Postgres is available

    my $url = 'http://www.postgresql.org/versions.rss';

    ## Grab the local version
    my $info = run_command('SELECT version() AS version');
    my $lversion = $info->{db}[0]{slurp}[0]{version};
    ## Make sure it is parseable and check for development versions
    if ($lversion !~ /\d+\.\d+\.\d+/) {
        if ($lversion =~ /(\d+\.\d+\S+)/) {
            add_ok msg('new-ver-dev', 'Postgres', $1);
            return;
        }
        add_unknown msg('new-ver-nolver', 'Postgres');
        return;
    }

    find_new_version('Postgres', $lversion, $url);

    return;

} ## end of check_new_version_pg


sub check_new_version_tnm {

    ## Check if a new version of tail_n_mail is available

    my $url = 'http://bucardo.org/tail_n_mail/latest_version.txt';
    find_new_version('tail_n_mail', 'tail_n_mail', $url);

    return;

} ## end of check_new_version_tnm


sub check_pgagent_jobs {
    ## Check for failed pgAgent jobs.
    ## Supports: Nagios
    ## Critical and warning are intervals.
    ## Example: --critical="1 hour"
    ## Example: --warning="2 hours"

    my ($warning, $critical) = validate_range({ type => 'time', any_warning => 1 });

    # Determine critcal warning column contents.
    my $is_crit = $critical && $warning
        ? "GREATEST($critical - EXTRACT('epoch' FROM NOW() - (jlog.jlgstart + jlog.jlgduration)), 0)"
        : $critical ? 1 : 0;

    # Determine max time to examine.
    my $seconds = $critical;
    $seconds = $warning if length $warning and
        (! length $critical or $warning > $critical);

    $SQL = qq{
        SELECT jlog.jlgid
             , job.jobname
             , step.jstname
             , slog.jslresult
             , slog.jsloutput
             , $is_crit AS critical
          FROM pgagent.pga_job job
          JOIN pgagent.pga_joblog     jlog ON job.jobid  = jlog.jlgjobid
          JOIN pgagent.pga_jobstep    step ON job.jobid  = step.jstjobid
          JOIN pgagent.pga_jobsteplog slog ON jlog.jlgid = slog.jsljlgid AND step.jstid = slog.jsljstid
         WHERE ((slog.jslresult = -1 AND step.jstkind='s') OR (slog.jslresult <> 0 AND step.jstkind='b'))
           AND EXTRACT('epoch' FROM NOW() - (jlog.jlgstart + jlog.jlgduration)) < $seconds
    };

    my $info = run_command($SQL);

    for $db (@{$info->{db}}) {
        my @rows = @{ $db->{slurp} } or do {
            add_ok msg('pgagent-jobs-ok');
            next;
        };

        if ($rows[0]{critical} !~ /^(?:[01]|\d+[.]\d+)$/) {
            add_unknown msg('invalid-query', $db->{slurp});
            next;
        }

        my ($is_critical, @msg);
        my $log_id = -1;
        for my $step (@rows) {
            my $output = $step->{jsloutput} || '(NO OUTPUT)';
            push @msg => "$step->{jslresult} $step->{jobname}/$step->{jstname}: $output";
            $is_critical ||= $step->{critical};
        }

        (my $msg = join '; ' => @msg) =~ s{\r?\n}{ }g;
        if ($is_critical) {
            add_critical $msg;
        }
        else {
            add_warning $msg;
        }
    }

    return;
}

sub check_pgbouncer_checksum {

    ## Verify the checksum of all pgbouncer settings
    ## Supports: Nagios, MRTG
    ## Not that the connection will be done on the pgbouncer database
    ## One of warning or critical must be given (but not both)
    ## It should run one time to find out the expected checksum
    ## You can use --critical="0" to find out the checksum
    ## You can include or exclude settings as well
    ## Example:
    ##  check_postgres_pgbouncer_checksum --critical="4e7ba68eb88915d3d1a36b2009da4acd"

    my ($warning, $critical) = validate_range({type => 'checksum', onlyone => 1});

    eval {
        require Digest::MD5;
    };
    if ($@) {
        ndie msg('checksum-nomd');
    }

    $SQL = 'SHOW CONFIG';
    my $info = run_command($SQL, { regex => qr[log_pooler_errors] });

    $db = $info->{db}[0];

    my $newstring = '';
    for my $r (@{$db->{slurp}}) {
        my $key = $r->{key};
        next if skip_item($key);
        $newstring .= "$r->{key} = $r->{value}\n";
    }

    if (! length $newstring) {
        add_unknown msg('no-match-set');
    }

    my $checksum = Digest::MD5::md5_hex($newstring);

    my $msg = msg('checksum-msg', $checksum);
    if ($MRTG) {
        $opt{mrtg} or ndie msg('checksum-nomrtg');
        do_mrtg({one => $opt{mrtg} eq $checksum ? 1 : 0, msg => $checksum});
    }
    if ($critical and $critical ne $checksum) {
        add_critical $msg;
    }
    elsif ($warning and $warning ne $checksum) {
        add_warning $msg;
    }
    elsif (!$critical and !$warning) {
        add_unknown $msg;
    }
    else {
        add_ok $msg;
    }

    return;

} ## end of check_pgbouncer_checksum

sub check_pgbouncer_backends {

    ## Check the number of connections to pgbouncer compared to
    ## max_client_conn
    ## Supports: Nagios, MRTG
    ## It makes no sense to run this more than once on the same cluster
    ## Need to be superuser, else only your queries will be visible
    ## Warning and criticals can take three forms:
    ## critical = 12 -- complain if there are 12 or more connections
    ## critical = 95% -- complain if >= 95% of available connections are used
    ## critical = -5 -- complain if there are only 5 or fewer connection slots left
    ## The former two options only work with simple numbers - no percentage or negative
    ## Can also ignore databases with exclude, and limit with include

    my $warning  = $opt{warning}  || '90%';
    my $critical = $opt{critical} || '95%';
    my $noidle   = $opt{noidle}   || 0;

    ## If only critical was used, remove the default warning
    if ($opt{critical} and !$opt{warning}) {
        $warning = $critical;
    }

    my $validre = qr{^(\-?)(\d+)(\%?)$};
    if ($critical !~ $validre) {
        ndie msg('pgb-backends-users', 'Critical');
    }
    my ($e1,$e2,$e3) = ($1,$2,$3);
    if ($warning !~ $validre) {
        ndie msg('pgb-backends-users', 'Warning');
    }
    my ($w1,$w2,$w3) = ($1,$2,$3);

    ## If number is greater, all else is same, and not minus
    if ($w2 > $e2 and $w1 eq $e1 and $w3 eq $e3 and $w1 eq '') {
        ndie msg('range-warnbig');
    }
    ## If number is less, all else is same, and minus
    if ($w2 < $e2 and $w1 eq $e1 and $w3 eq $e3 and $w1 eq '-') {
        ndie msg('range-warnsmall');
    }
    if (($w1 and $w3) or ($e1 and $e3)) {
        ndie msg('range-neg-percent');
    }

    ## Grab information from the config
    $SQL = 'SHOW CONFIG';

    my $info = run_command($SQL, { regex => qr{\d+}, emptyok => 1 } );

    ## Default values for information gathered
    my $limit = 0;

    ## Determine max_client_conn
    for my $r (@{$info->{db}[0]{slurp}}) {
        if ($r->{key} eq 'max_client_conn') {
            $limit = $r->{value};
            last;
        }
    }

    ## Grab information from pools
    $SQL = 'SHOW POOLS';

    $info = run_command($SQL, { regex => qr{\d+}, emptyok => 1 } );

    $db = $info->{db}[0];

    my $total = 0;
    my $grandtotal = @{$db->{slurp}};

    for my $r (@{$db->{slurp}}) {

        ## Always want perf to show all
        my $nwarn=$w2;
        my $ncrit=$e2;
        if ($e1) {
            $ncrit = $limit-$e2;
        }
        elsif ($e3) {
            $ncrit = (int $e2*$limit/100);
        }
        if ($w1) {
            $nwarn = $limit-$w2;
        }
        elsif ($w3) {
            $nwarn = (int $w2*$limit/100)
        }

        if (! skip_item($r->{database})) {
            my $current = $r->{cl_active} + $r->{cl_waiting};
            $db->{perf} .= " '$r->{database}'=$current;$nwarn;$ncrit;0;$limit";
            $total += $current;
        }
    }

    if ($MRTG) {
        $stats{$db->{dbname}} = $total;
        $statsmsg{$db->{dbname}} = msg('pgb-backends-mrtg', $db->{dbname}, $limit);
        return;
    }

    if (!$total) {
        if ($grandtotal) {
            ## We assume that exclude/include rules are correct, and we simply had no entries
            ## at all in the specific databases we wanted
            add_ok msg('pgb-backends-none');
        }
        else {
            add_unknown msg('no-match-db');
        }
        return;
    }

    my $percent = (int $total / $limit*100) || 1;
    my $msg = msg('pgb-backends-msg', $total, $limit, $percent);
    my $ok = 1;

    if ($e1) { ## minus
        $ok = 0 if $limit-$total <= $e2;
    }
    elsif ($e3) { ## percent
        my $nowpercent = $total/$limit*100;
        $ok = 0 if $nowpercent >= $e2;
    }
    else { ## raw number
        $ok = 0 if $total >= $e2;
    }
    if (!$ok) {
        add_critical $msg;
        return;
    }

    if ($w1) {
        $ok = 0 if $limit-$total <= $w2;
    }
    elsif ($w3) {
        my $nowpercent = $total/$limit*100;
        $ok = 0 if $nowpercent >= $w2;
    }
    else {
        $ok = 0 if $total >= $w2;
    }
    if (!$ok) {
        add_warning $msg;
        return;
    }

    add_ok $msg;

    return;

} ## end of check_pgbouncer_backends



sub check_pgb_pool {

    # Check various bits of the pgbouncer SHOW POOLS ouptut
    my $stat = shift;
    my ($warning, $critical) = validate_range({type => 'positive integer'});

    $SQL = 'SHOW POOLS';
    my $info = run_command($SQL, { regex => qr[$stat] });

    $db = $info->{db}[0];
    my $output = $db->{slurp};
    my $gotone = 0;
    for my $i (@$output) {
        next if skip_item($i->{database});
        my $msg = "$i->{database}=$i->{$stat}";

        if ($MRTG) {
            $stats{$i->{database}} = $i->{$stat};
            $statsmsg{$i->{database}} = msg('pgbouncer-pool', $i->{database}, $stat, $i->{$stat});
            next;
        }

        if ($critical and $i->{$stat} >= $critical) {
            add_critical $msg;
        }
        elsif ($warning and $i->{$stat} >= $warning) {
            add_warning $msg;
        }
        else {
            add_ok $msg;
        }
    }

    return;

} ## end of check_pgb_pool


sub check_prepared_txns {

    ## Checks age of prepared transactions
    ## Most installations probably want no prepared_transactions
    ## Supports: Nagios, MRTG

    my ($warning, $critical) = validate_range
        ({
          type              => 'seconds',
          default_warning   => '1',
          default_critical  => '30',
        });

    my $SQL = q{
SELECT database, ROUND(EXTRACT(epoch FROM now()-prepared)) AS age, prepared
FROM pg_prepared_xacts
ORDER BY prepared ASC
};

    my $info = run_command($SQL, {regex => qr[\w+], emptyok => 1 } );

    my $msg = msg('preptxn-none');
    my $found = 0;
    for $db (@{$info->{db}}) {
        my (@crit,@warn,@ok);
        my ($maxage,$maxdb) = (0,''); ## used by MRTG only
      ROW: for my $r (@{$db->{slurp}}) {
            my ($dbname,$age,$date) = ($r->{database},$r->{age},$r->{prepared});
            $found = 1 if ! $found;
            next ROW if skip_item($dbname);
            $found = 2;
            if ($MRTG) {
                if ($age > $maxage) {
                    $maxdb = $dbname;
                    $maxage = $age;
                }
                elsif ($age == $maxage) {
                    $maxdb .= sprintf "%s$dbname", length $maxdb ? ' | ' : '';
                }
                next;
            }

            $msg = "$dbname=$date ($age)";
            $db->{perf} .= sprintf ' %s=%ss;%s;%s',
                perfname($dbname), $age, $warning, $critical;
            if (length $critical and $age >= $critical) {
                push @crit => $msg;
            }
            elsif (length $warning and $age >= $warning) {
                push @warn => $msg;
            }
            else {
                push @ok => $msg;
            }
        }
        if ($MRTG) {
            do_mrtg({one => $maxage, msg => $maxdb});
        }
        elsif (0 == $found) {
            add_ok msg('preptxn-none');
        }
        elsif (1 == $found) {
            add_unknown msg('no-match-db');
        }
        elsif (@crit) {
            add_critical join ' ' => @crit;
        }
        elsif (@warn) {
            add_warning join ' ' => @warn;
        }
        else {
            add_ok join ' ' => @ok;
        }
    }

    return;

} ## end of check_prepared_txns


sub check_query_runtime {

    ## Make sure a known query runs at least as fast as we think it should
    ## Supports: Nagios, MRTG
    ## Warning and critical are time limits, defaulting to seconds
    ## Valid units: s[econd], m[inute], h[our], d[ay]
    ## Does a "EXPLAIN ANALYZE SELECT COUNT(1) FROM xyz"
    ## where xyz is given by the option --queryname
    ## This could also be a table or a function, or course, but must be a 
    ## single word. If a function, it must be empty (with "()")
    ## Examples:
    ## --warning="100s" --critical="120s" --queryname="speedtest1"
    ## --warning="5min" --critical="15min" --queryname="speedtest()"

    my ($warning, $critical) = validate_range({type => 'time'});

    my $queryname = $opt{queryname} || '';

    if ($queryname !~ /^[\w\_\.]+(?:\(\))?$/) {
        ndie msg('runtime-badname');
    }

    $SQL = "EXPLAIN ANALYZE SELECT COUNT(1) FROM $queryname";
    my $info = run_command($SQL);

    for $db (@{$info->{db}}) {
        if (! exists $db->{slurp}[0]{queryplan}) {
            add_unknown msg('invalid-query', $db->{slurp});
            next;
        }
        my $totalms = -1;
        for my $r (@{$db->{slurp}}) {
            if ($r->{queryplan} =~ / (\d+\.\d+) ms/) {
                $totalms = $1;
            }
        }
        my $totalseconds = sprintf '%.2f', $totalms / 1000.0;
        if ($MRTG) {
            $stats{$db->{dbname}} = $totalseconds;
            next;
        }
        $db->{perf} = sprintf '%s=%ss;%s;%s',
            perfname(msg('query-time')), $totalseconds, $warning, $critical;
        my $msg = msg('runtime-msg', $totalseconds);
        if (length $critical and $totalseconds >= $critical) {
            add_critical $msg;
        }
        elsif (length $warning and $totalseconds >= $warning) {
            add_warning $msg;
        }
        else {
            add_ok $msg;
        }
    }

    $MRTG and do_mrtg_stats(msg('runtime-badmrtg'));

    return;

} ## end of check_query_runtime


sub check_query_time {

    ## Check the length of running queries

    check_txn_idle('qtime',
                   msg('queries'),
                   msg('query-time'),
                   'query_start',
                   q{query_start IS NOT NULL AND current_query NOT LIKE '<IDLE>%'});

    return;

} ## end of check_query_time


sub check_relation_size {

    my $relkind = shift || 'relation';

    ## Check the size of one or more relations
    ## Supports: Nagios, MRTG
    ## By default, checks all relations
    ## Can check specific one(s) with include
    ## Can ignore some with exclude
    ## Warning and critical are bytes
    ## Valid units: b, k, m, g, t, e
    ## All above may be written as plural or with a trailing 'g'
    ## Limit to a specific user (relation owner) with the includeuser option
    ## Exclude users with the excludeuser option

    my ($warning, $critical) = validate_range({type => 'size'});

    $SQL = sprintf q{
SELECT pg_relation_size(c.oid) AS rsize,
  pg_size_pretty(pg_relation_size(c.oid)) AS psize,
  relkind, relname, nspname
FROM pg_class c, pg_namespace n WHERE (relkind = %s) AND n.oid = c.relnamespace
},
    $relkind eq 'table' ? q{'r'}
    : $relkind eq 'index' ? q{'i'}
    : q{'r' OR relkind = 'i'};

    if ($opt{perflimit}) {
        $SQL .= " ORDER BY 1 DESC LIMIT $opt{perflimit}";
    }

    if ($USERWHERECLAUSE) {
        $SQL =~ s/ WHERE/, pg_user u WHERE u.usesysid=c.relowner$USERWHERECLAUSE AND/;
    }

    my $info = run_command($SQL, {emptyok => 1});

    my $found = 0;
    for $db (@{$info->{db}}) {

        $found = 1;
        if ($db->{slurp}[0]{rsize} !~ /\d/ and $USERWHERECLAUSE) {
            $stats{$db->{dbname}} = 0;
            add_ok msg('no-match-user');
            next;
        }

        my ($max,$pmax,$kmax,$nmax,$smax) = (-1,0,0,'?','?');

      ROW: for my $r (@{$db->{slurp}}) {
            my ($size,$psize,$kind,$name,$schema) = @$r{qw/ rsize psize relkind relname nspname/};

            next ROW if skip_item($name, $schema);

            my $nicename = $kind eq 'r' ? "$schema.$name" : $name;

            $db->{perf} .= sprintf '%s%s=%sB;%s;%s',
                $VERBOSE==1 ? "\n" : ' ',
                perfname($nicename), $size, $warning, $critical;
            ($max=$size, $pmax=$psize, $kmax=$kind, $nmax=$name, $smax=$schema) if $size > $max;
        }
        if ($max < 0) {
            add_unknown msg('no-match-rel');
            next;
        }
        if ($MRTG) {
            my $msg = sprintf 'DB: %s %s %s%s',
                $db->{dbname},
                $kmax eq 'i' ? 'INDEX:' : 'TABLE:',
                $kmax eq 'i' ? '' : "$smax.",
                $nmax;
            do_mrtg({one => $max, msg => $msg});
            next;
        }

        my $msg;
        if ($relkind eq 'relation') {
            if ($kmax eq 'r') {
                $msg = msg('relsize-msg-relt', "$smax.$nmax", $pmax);
            }
            else {
                $msg = msg('relsize-msg-reli', $nmax, $pmax);
            }
        }
        elsif ($relkind eq 'table') {
            $msg = msg('relsize-msg-tab', "$smax.$nmax", $pmax);
        }
        else {
            $msg = msg('relsize-msg-ind', $nmax, $pmax);
        }
        if (length $critical and $max >= $critical) {
            add_critical $msg;
        }
        elsif (length $warning and $max >= $warning) {
            add_warning $msg;
        }
        else {
            add_ok $msg;
        }
    }

    return;

} ## end of check_relation_size


sub check_table_size {
    return check_relation_size('table');
}
sub check_index_size {
    return check_relation_size('index');
}


sub check_replicate_row {

    ## Make an update on one server, make sure it propogates to others
    ## Supports: Nagios, MRTG
    ## Warning and critical are time to replicate to all slaves

    my ($warning, $critical) = validate_range({type => 'time', leastone => 1, forcemrtg => 1});

    if ($warning and $critical and $warning > $critical) {
        ndie msg('range-warnbig');
    }

    if (!$opt{repinfo}) {
        ndie msg('rep-noarg');
    }
    my @repinfo = split /,/ => ($opt{repinfo} || '');
    if ($#repinfo != 5) {
        ndie msg('rep-badarg');
    }
    my ($table,$pk,$id,$col,$val1,$val2) = (@repinfo);

    ## Quote everything, just to be safe (e.g. columns named 'desc')
    $table =~ s/([^\.]+)/\"$1\"/g;
    $pk    = qq{"$pk"};
    $col   = qq{"$col"};

    if ($val1 eq $val2) {
        ndie msg('rep-duh');
    }

    $SQL = qq{UPDATE $table SET $col = 'X' WHERE $pk = '$id'};
    (my $update1 = $SQL) =~ s/X/$val1/;
    (my $update2 = $SQL) =~ s/X/$val2/;
    my $select = qq{SELECT $col AS c FROM $table WHERE $pk = '$id'};

    ## Are they the same on both sides? Must be yes, or we error out

    ## We assume this is a single server
    my $info1 = run_command($select);
    ## Squirrel away the $db setting for later
    my $sourcedb = $info1->{db}[0];
    if (!defined $sourcedb) {
        ndie msg('rep-norow', "$table.$col");
    }
    my $value1 = $info1->{db}[0]{slurp}[0]{c} || '';

    my $numslaves = @{$info1->{db}} - 1;
    for my $d ( @{$info1->{db}}[1 .. $numslaves] ) {
        my $value2 = $d->{slurp}[0]{c} || '';
        if ($value1 ne $value2) {
            ndie msg('rep-notsame');
        }
    }
    if ($numslaves < 1) {
        ndie msg('rep-noslaves');
    }

    my ($update,$newval);
    UNINITOK: {
        no warnings 'uninitialized';
        if ($value1 eq $val1) {
            $update = $update2;
            $newval = $val2;
        }
        elsif ($value1 eq $val2) {
            $update = $update1;
            $newval = $val1;
        }
        else {
            ndie msg('rep-wrongvals', $value1, $val1, $val2);
        }
    }

    $info1 = run_command($update, { dbnumber => 1, failok => 1 } );

    ## Make sure the update worked
    if (! defined $info1->{db}[0]) {
        ndie msg('rep-sourcefail');
    }

    my $err = $info1->{db}[0]{error} || '';
    if ($err) {
        $err =~ s/ERROR://; ## e.g. Slony read-only
        ndie $err;
    }

    ## Start the clock
    my $starttime = time();

    ## Loop until we get a match, check each in turn
    my %slave;
    my $time = 0;
    LOOP: {
        my $info2 = run_command($select);
        ## Reset for final output
        $db = $sourcedb;

        my $slave = 0;
        for my $d (@{$info2->{db}}[1 .. $numslaves]) {
            $slave++;
            next if exists $slave{$slave};
            my $value2 = $d->{slurp}[0]{c};
            $time = $db->{totaltime} = time - $starttime;
            if ($value2 eq $newval) {
                $slave{$slave} = $time;
                next;
            }
            if ($warning and $time > $warning) {
                $MRTG and do_mrtg({one => 0, msg => $time});
                add_warning msg('rep-fail', $slave);
                return;
            }
            elsif ($critical and $time > $critical) {
                $MRTG and do_mrtg({one => 0, msg => $time});
                add_critical msg('rep-fail', $slave);
                return;
            }
        }
        ## Did they all match?
        my $k = keys %slave;
        if (keys %slave >= $numslaves) {
            $MRTG and do_mrtg({one => $time});
            add_ok msg('rep-ok');
            return;
        }
        sleep 1;
        redo;
    }

    $MRTG and ndie msg('rep-timeout', $time);
    add_unknown msg('rep-unknown');
    return;

} ## end of check_replicate_row


sub check_same_schema {

    ## Verify that all relations inside two or more databases are the same
    ## Supports: Nagios
    ## Include and exclude are supported
    ## Warning and critical are not used
    ## The filter argument is supported

    ## We override the usual $db->{totaltime} with our own counter
    my $start = [gettimeofday()];

    ## Check for filtering rules, then store inside opt{filtered}
    my %filter;
    if (exists $opt{filter}) {
        for my $item (@{ $opt{filter} }) {
            ## Can separate by whitespace or commas
            for my $phrase (split /[\s,]+/ => $item) {

                ## Can be plain (e.g. nouser) or regex based exclusion, e.g. nouser=bob
                next if $phrase !~ /(\w+)=?\s*(.*)/o;
                my ($name,$regex) = (lc $1,$2||'');

                ## Names are standardized with regards to plurals and casing
                $name =~ s/([aeiou])s$/$1/o;
                $name =~ s/s$//o;

                if (! length $regex) {
                    $filter{"$name"} = 1;
                }
                else {
                    push @{$filter{"${name}_regex"}} => $regex;
                }
            }
            $VERBOSE >= 3 and warn Dumper \%filter;
        }
    }
    $opt{filtered} = \%filter;

    ## See how many databases we are using
    my $numdbs = @targetdb;
    $VERBOSE >= 3 and warn "Number of databases is $numdbs\n";

    ## If only a single database is given, this is a time-based comparison
    ## In other words, we write and read a local file
    my $samedb = 0;
    if (1 == $numdbs) {
        $samedb = 1;
        $numdbs = 2;
    }

    ## Sanity check
    if ($opt{suffix} and ! $samedb) {
        ndie msg('ss-suffix');
    }

    ## Version information about each database, by number
    my %dbver;

    ## Verify we can connect to each database, and grab version information
    for my $num (1..$numdbs) {

        ## No need to check the same database twice!
        last if $samedb and $num > 1;

        $SQL = 'SELECT version()';
        my $info = run_command($SQL, { dbnumber => $num } );

        ## We need a global $db, so we'll use the first database
        $db = $info->{db}[0] if 1 == $num;

        my $foo = $info->{db}[0];
        my $version = $foo->{slurp}[0]{version};
        $version =~ /\D+(\d+\.\d+)(\S+)/i or die qq{Invalid version: $version\n};
        my ($full,$major,$revision) = ("$1$2",$1,$2);
        $revision =~ s/^\.//;
        $dbver{$num} = {
            full     => $version,
            version  => $full,
            major    => $major,
            revision => $revision,
        };

        $targetdb[$num-1]{pgversion} = $full;

    }

    ## An ordered list of all the things we check.
    ## Order is important here, as when reporting, some things
    ## can mask reporting on others (e.g. no need to report missing tables
    ## if the entire schema has already been reported as missing)
    ## We also indicate which columns should be ignored when comparing,
    ## as well as which columns are of a 'list' nature
    my @catalog_items = (
        [user       => 'usesysid',                                'useconfig' ],
        [language   => 'laninline,lanplcallfoid,lanvalidator',    ''          ],
        [operator   => '',                                        ''          ],
        [type       => '',                                        ''          ],
        [schema     => '',                                        ''          ],
        [function   => 'source_checksum,prolang,prorettype',      ''          ],
        [table      => 'reltype,relfrozenxid,relminmxid,relpages,
                        reltuples,relnatts,relallvisible',        ''          ],
        [view       => 'reltype',                                 ''          ],
        [sequence   => 'reltype,log_cnt,relnatts,is_called',      ''          ],
        [index      => 'relpages,reltuples,indpred,indclass,
                        indexprs,indcheckxmin',                   ''          ],
        [trigger    => '',                                        ''          ],
        [constraint => 'conbin',                                  ''          ],
        [column     => 'atttypid,attnum,attbyval',                ''          ],
    );

    ## Where we store all the information, per-database
    my %thing;

    my $saved_db;
    for my $x (1..$numdbs) {

        if ($x > 1 and $samedb) {
            ## This means we are looking at a single database over time
            ## We load the stored information into the current $dbinfo
            my $filename = audit_filename();

            if (! -e $filename) {
                ## We've not saved any information about this database yet
                ## Store the info and exit!
                my $version = $dbver{1}{version};
                write_audit_file({ file => $filename, 'same_schema' => 1,
                                   info => $thing{1}, pgversion => $version });
                print msg('ss-createfile', $filename) . "\n";
                exit 0;
            }

            ## Meta-information from the file
            my ($conninfo,$ctime,$cversion,$pgversion,$cdbname,$chost,$cport,$cuser);

            ($thing{$x},$conninfo,$ctime,$cversion,$pgversion,$cdbname,$chost,$cport,$cuser)
                = read_audit_file($filename);

            ## Count total objects
            my $totalcount = 0;
            for (keys %{ $thing{$x} }) {
                $totalcount += keys %{ $thing{$x}{$_} };
            }

            ## Add the meta info back into the targetdb
            push @targetdb, {
                filename  => $filename,
                conninfo  => $conninfo,
                ctime     => $ctime,
                cversion  => $cversion,
                dbname    => $cdbname,
                port      => $cport,
                host      => $chost,
                dbuser    => $cuser,
                pgversion => $pgversion,
                objects   => $totalcount,
            };

            next;

        } ## end if samedb

        ## Hash of this round's information
        my $dbinfo;

        for (@catalog_items) {
            my $name = $_->[0];
            $dbinfo->{$name} = find_catalog_info($name, $x, $dbver{$x});
        }

        ## TODO:
        ## operator class, cast, aggregate, conversion, domain, tablespace, foreign tables
        ## foreign server, wrapper, collation, extensions, roles?

        ## Map the oid back to the user, for ease later on
        for my $row (values %{ $dbinfo->{user} }) {
            $dbinfo->{useroid}{$row->{usesysid}} = $row->{usename};
        }

        $thing{$x} = $dbinfo;

        ## Count total objects
        my $totalcount = 0;
        for (keys %{ $thing{$x} }) {
            $totalcount += keys %{ $thing{$x}{$_} };
        }

        $targetdb[$x-1]{objects} = $totalcount;


    } ## end each database to query

    ## Start comparing, and put any differences into %fail
    my %fail;

    ## Ugly, but going to use this as a global for the subroutines below:
    $opt{failcount} = 0;

    ## Simple checks that items exist on each database
    for (@catalog_items) {
        my $name = $_->[0];
        $fail{$name}{exists} = schema_item_exists($name, \%thing);
    }

    ## Now check for some more specific items for each item class.
    ## For many of these, we want to compare all columns except for
    ## certain known exceptions (e.g. anything oid-based)
    ## Because we may go across versions, if the column does not exist
    ## somewhere, it is simply silently ignored
    ## Some items are lists (e.g. acls) and must be treated differently

    for (@catalog_items) {
        my ($name,$ignore,$lists) = @$_;
        $fail{$name}{diff} = schema_item_differences({
            items  => \%thing,
            name   => $name,
            ignore => $ignore,
            lists  => $lists,
        });
    }

    ## Remove empty hashes for a cleaner debug dump
    for (keys %fail) {
        if (exists $fail{$_}{diff} and ! keys %{ $fail{$_}{diff} }) {
            delete $fail{$_}{diff};
        }
    }

    ## Set the total time
    $db->{totaltime} = sprintf '%.2f', tv_interval($start);

    ## Before we outpu any results, rewrite the audit file if needed
    ## We do this if we are reading from a saved file,
    ## and the "replace" argument is set
    if ($samedb and $opt{replace}) {
        my $filename = audit_filename();
        if ( -e $filename) {
            ## Move the old one to a backup version
            my $backupfile = "$filename.backup";
            rename $filename, $backupfile;
        }
        my $version = $dbver{1}{version};
        write_audit_file({ file => $filename, 'same_schema' => 1,
                           info => $thing{1}, pgversion => $version });
        ## Cannot print this message as we are outputting Nagios stuff
        #print msg('ss-createfile', $filename) . "\n";
    }

    ## Comparison is done, let's report the results
    if (! $opt{failcount}) {
        add_ok msg('ss-matched');
        return;
    }

    ## Build a pretty message giving all the gory details
    my $msg = '';

    ## Adjust the output based on the leading message sizes
    my $maxsize = 1;
    my $msg_exists = msg('ss-existson');
    my $msg_missing = msg('ss-missingon');
    $maxsize = length $msg_exists if length $msg_exists > $maxsize;
    $maxsize = length $msg_missing if length $msg_missing > $maxsize;

    ## Walk through each item type in alphabetical order and output the differences
    for (@catalog_items) {
        my $item = $_->[0];

        ## Pretty name for this type of item. No matches is okay!
        $opt{nomsgok} = 1;
        my $pitem = msg($item) || ucfirst $item;
        $opt{nomsgok} = 0;

        ## See if there are any items of this class that only exist on some
        my $e = $fail{$item}{exists};
        if (keys %$e) {
            for my $name (sort keys %$e) {
                ## We do not want to report twice on things that appear inside of schemas
                ## However, we do report if the schema *does* exist on any of the missing databases
                if ($item ne 'schema' and $name =~ /(.+?)\./) {
                    my $schema = $1;
                    ## How many databases do not have this?
                    my $missingcount = keys %{ $e->{$name}{nothere} };
                    my $noschemacount = 0;
                    for my $db (keys %{ $e->{$name}{nothere} }) {
                        if (exists $fail{schema}{exists}{$schema}{nothere}{$db}) {
                            $noschemacount++;
                        }
                    }
                    if ($missingcount == $noschemacount) {
                        next;
                    }
                }

                ## Show the list of the item, and a CSV of which databases have it and which don't
                my $isthere = join ', ' => sort { $a<=>$b } keys %{ $e->{$name}{isthere} };
                my $nothere = join ', ' => sort { $a<=>$b } keys %{ $e->{$name}{nothere} };
                $msg .= sprintf "%s\n  %-*s %s\n  %-*s %s\n",
                    msg('ss-noexist', $pitem, $name),
                    $maxsize, $msg_exists,
                    $isthere,
                    $maxsize, $msg_missing,
                    $nothere;
            }
        }

        ## See if there are any items for this class that have differences
        my $d = $fail{$item}{diff};
        if (keys %$d) {

            for my $name (sort keys %$d) {
                my $tdiff = $d->{$name};

                ## Any raw column differences?
                if (exists $tdiff->{coldiff}) {
                    my @msg;

                    for my $col (sort keys %{ $tdiff->{coldiff} }) {

                        ## Do not show index 'owners': already covered by the table itself
                        if ($col eq 'owner' and $item eq 'index') {
                            next;
                        }

                        ## Do not show column number differences if filtered out with "noposition"
                        if ($item eq 'column'
                            and $col eq 'column_number'
                            and $opt{filtered}{noposition}) {
                            next;
                        }

                        ## Do not show function body differences if filtered out with "nofuncbody"
                        ## Also skip if the equivalent 'dash' and 'empty'
                        if ($item eq 'function'
                            and $col eq 'prosrc') {

                            next if $opt{filtered}{nofuncbody};
                            my ($one,$two);
                            for my $db (sort keys %{ $tdiff->{coldiff}{$col} }) {
                                if (defined $one) {
                                    $two = $tdiff->{coldiff}{$col}{$db};
                                }
                                else {
                                    $one = $tdiff->{coldiff}{$col}{$db};
                                }
                            }
                            next if $one eq '-' and $two eq '';
                            next if $one eq '' and $two eq '-';
                        }

                        ## If we are doing a historical comparison, skip some items
                        if ($samedb) {
                            if ($item eq 'sequence'
                                and $col eq 'last_value') {
                                next;
                            }
                        }

                        push @msg => sprintf " %s\n", msg('ss-different', $col);
                        for my $db (sort keys %{ $tdiff->{coldiff}{$col} }) {
                            push @msg => sprintf "    %s %s: %s\n",
                                ucfirst msg('database'),
                                $db,
                                $tdiff->{coldiff}{$col}{$db};
                        }
                    }

                    if (@msg) {
                        $msg .= qq{$pitem "$name":\n};
                        $msg .= $_ for @msg;
                    }
                    else {
                        ## Everything got filtered out, so decrement this item
                        $opt{failcount}--;
                    }
                }

                ## Any multi-item column differences?
                if (exists $tdiff->{list}) {

                    my @msg;
                    for my $col (sort keys %{ $tdiff->{list} }) {

                        ## Exclude permissions if 'noperm' filter is set
                        if ($col =~ /.acl$/ and $opt{filtered}{noperm}) {
                            next;
                        }

                        if (exists $tdiff->{list}{$col}{exists}) {
                            my $ex = $tdiff->{list}{$col}{exists};
                            for my $name (sort keys %$ex) {
                                push @msg => sprintf qq{  "%s":\n    %s\n},
                                    $col,
                                    msg('ss-notset', $name);
                                my $isthere = join ', ' => sort { $a<=>$b } keys %{ $ex->{$name}{isthere} };
                                my $nothere = join ', ' => sort { $a<=>$b } keys %{ $ex->{$name}{nothere} };
                                push @msg => sprintf "      %-*s %s\n      %-*s %s\n",
                                    $maxsize, $msg_exists,
                                    $isthere,
                                    $maxsize, $msg_missing,
                                    $nothere;
                            }
                        }
                        if (exists $tdiff->{list}{$col}{diff}) {
                            for my $setting (sort keys %{ $tdiff->{list}{$col}{diff} }) {

                                push @msg => sprintf qq{  "%s":\n    %s\n},
                                    $col,
                                    msg('ss-different', $setting);
                                for my $db (sort keys %{ $tdiff->{list}{$col}{diff}{$setting} }) {
                                    my $val = $tdiff->{list}{$col}{diff}{$setting}{$db};
                                    push @msg => sprintf "      %s %s: %s\n",
                                        ucfirst msg('database'),
                                        $db,
                                        $val;
                                }
                            }
                        }
                    }

                    if (@msg) {
                        $msg .= qq{$pitem "$name":\n};
                        $msg .= $_ for @msg;
                    }
                    else {
                        ## No message means it was all filtered out, so we decrment the master count
                        $opt{failcount}--;
                    }
                }
            }
        }
    }

    ## We may have no items due to exclusions!
    if (! $opt{failcount}) {
        add_ok msg('ss-matched');
        return;
    }

    $db->{perf} = "\n$msg";
    add_critical msg('ss-failed', $opt{failcount});
    return;

} ## end of check_same_schema


sub audit_filename {

    ## Generate the name of the file to store audit information

    ## Get the connection information for this connection
    my $filename = run_command('foo', { conninfo => 1 });
    ## Do not care about the username
    $filename =~ s/ user=(.+)//;
    ## Strip out the host if not used
    $filename =~ s/ host=<none>//;
    ## Replace any other spaces
    $filename =~ s/ /./g;
    ## Equals have to be escaped, so we'll change them to a dot
    $filename =~ s/=/./g;
    ## The final filename to use
    $filename = "check_postgres.audit.$filename";

    ## The host name may have slashes, so change to underscores
    $filename =~ s{\/}{_}g;

    ## Got a user-supplied extension? Add it now.
    if ($opt{suffix}) {
        $filename .= ".$opt{suffix}";
    }

    return $filename;

} ## end of audit_filename


sub write_audit_file {

    ## Save a new copy of the audit file
    my $arg = shift || {};
    my $filename = $arg->{filename} || audit_filename();
    my $info = $arg->{info} || die;

    ## Create a connection information string
    my $row = $targetdb[0];
    my $conninfo = sprintf '%s%s%s%s',
        defined $row->{port} ? qq{port=$row->{port} } : '',
        defined $row->{host} ? qq{host=$row->{host} } : '',
        defined $row->{dbname} ? qq{dbname=$row->{dbname} } : '',
        defined $row->{dbuser} ? qq{user=$row->{dbuser} } : '';

    open my $fh, '>', $filename or die qq{Could not open "$filename": $!\n};
    print {$fh} "## Audit file for check_postgres\n";
    print {$fh} "## CP version: $VERSION\n";
    print {$fh} "## PG version: $arg->{pgversion}\n";
    printf {$fh} "## Created: %s\n", scalar localtime();
    print {$fh} "## Connection: $conninfo\n";
    print {$fh} "## Database name: $row->{dbname}\n";
    print {$fh} "## Host: $row->{host}\n";
    print {$fh} "## Port: $row->{port}\n";
    print {$fh} "## User: $row->{dbuser}\n";
    if ($arg->{same_schema}) {
        print {$fh} "## Start of same_schema information:\n";
        {
            local $Data::Dumper::Indent = 1;
            print {$fh} Dumper $info;
        }
        print {$fh} "## End of same_schema information\n";
    }

    close $fh or warn qq{Could not close "$filename": $!\n};

} ## end of write_audit_file


sub read_audit_file {

    ## Read in the data from a historical file
    ## Returns four items:
    ## 1. The standard catalog structure that was saved
    ## 2. Connection information string
    ## 3. Date the file was created
    ## 4. The version it was created with

    my $filename = shift;

    open my $fh, '<', $filename or die qq{Could not open "$filename": $!\n};
    my $inside = 0;
    my $data = '';
    my ($conninfo,$ctime,$cversion,$pgversion) = ('???','???','???','???');
    my ($cdbname,$chost,$cport,$cuser) = ('???','???','???','???');
    while (<$fh>) {
        if (!$inside) {
            if (/Start of same_schema/) {
                $inside = 1;
            }
            elsif (/CP version: (.+)/) {
                $cversion = $1;
            }
            elsif (/PG version: (.+)/) {
                $pgversion = $1;
            }
            elsif (/Created: (.+)/) {
                $ctime = $1;
            }
            elsif (/Connection: (.+)/) {
                $conninfo = $1;
            }
            elsif (/Database name: (.+)/) {
                $cdbname = $1;
            }
            elsif (/Host: (.+)/) {
                $chost = $1;
            }
            elsif (/Port: (.+)/) {
                $cport = $1;
            }
            elsif (/User: (.+)/) {
                $cuser = $1;
            }
        }
        elsif (/End of same_schema/) {
            last;
        }
        else {
            $data .= $_;
        }
    }
    close $fh or warn qq{Could not close "$filename": $!\n};

    my $POSTGRES1;
    eval $data; ## no critic (ProhibitStringyEval)
    if ($@) {
        die qq{Failed to parse file "$filename": $@\n};
    }
    return $POSTGRES1, $conninfo, $ctime, $cversion,
           $pgversion, $cdbname, $chost, $cport, $cuser;

} ## end of read_audit_file


sub schema_item_exists {

    ## Compare a certain class of items across all databases for existence
    ## Returns a hashref of item names, with "isthere" and "nothere"
    ## with keys of database numbers underneath that

    my $item_class = shift;
    my $itemhash = shift;

    ## Things that failed to match:
    my %nomatch;

    my $key = "no${item_class}_regex";
    my $exclude_regex = exists $opt{filtered}->{$key} ? $opt{filtered}->{$key} : [];

    for my $db1 (sort keys %$itemhash) {
        for my $db2 (sort keys %$itemhash) {
            next if $db1 == $db2;
            for my $name (sort keys %{ $itemhash->{$db1}{$item_class} }) {

                ## Can exclude by 'filter' based regex
                next if grep { $name eq $_ } @$exclude_regex;

                if (! exists $itemhash->{$db2}{$item_class}{$name}) {

                    ## Special exception for columns: do not add if the table is non-existent
                    if ($item_class eq 'column') {
                        (my $tablename = $name) =~ s/(.+)\..+/$1/;
                        next if ! exists $itemhash->{$db2}{table}{$tablename};
                    }

                    ## Special exception for triggers: do not add if the table is non-existent
                    if ($item_class eq 'trigger') {
                        my $it = $itemhash->{$db1}{$item_class}{$name};
                        my $tablename = "$it->{tschema}.$it->{tname}";
                        next if ! exists $itemhash->{$db2}{table}{$tablename};
                    }

                    $nomatch{$name}{isthere}{$db1} = 1;
                    $nomatch{$name}{nothere}{$db2} = 1;
                }
            }
        }
    }

    ## Increment our fail count once per item mismatch
    $opt{failcount} += keys %nomatch;

    return \%nomatch;

} ## end of schema_item_exists


sub schema_item_differences {

    ## Compare a certain class of items across all databases for differences
    ## Takes a hashref of argument, including:
    ##   name: the item class name
    ##   items: the main hashref of all items
    ##   ignore: which fields to ignore. CSV
    ##   lists: which fields are lists. CSV
    ## Modified the items hashref by incrementing items->{failcount}
    ## Returns s hashref of item names, with details as to the diffs therein

    my $arg = shift;

    my $item_class = $arg->{name} or die;
    my $itemhash = $arg->{items} or die;

    ## Things we completely ignore:
    my $ignore = { oid => 1 };
    if (exists $arg->{ignore}) {
        for my $item (split /\s*,\s*/ => $arg->{ignore}) {
            $ignore->{$item} = 1;
        }
    }

    ## Things that are handled as lists:
    my $lists = {};
    if (exists $arg->{lists}) {
        for my $item (split /\s*,\s*/ => $arg->{lists}) {
            $lists->{$item} = 1;
        }
    }

    ## The final lists of mismatched items we pass back
    my %nomatch;

    my $key = "no${item_class}_regex";
    my $exclude_regex = exists $opt{filtered}->{$key} ? $opt{filtered}->{$key} : [];

    for my $db1 (sort keys %$itemhash) {
        for my $db2 (sort keys %$itemhash) {
            next if $db1 >= $db2;
            for my $name (sort keys %{ $itemhash->{$db1}{$item_class} }) {

                ## Can exclude by 'filter' based regex
                next if grep { $name eq $_ } @$exclude_regex;

                ## This case has already been handled:
                next if ! exists $itemhash->{$db2}{$item_class}{$name};

                ## Special exception for columns: do not add if the table is non-existent
                if ($item_class eq 'column') {
                    (my $tablename = $name) =~ s/(.+)\..+/$1/;
                    next if ! exists $itemhash->{$db2}{table}{$tablename};
                }

                my $one = $itemhash->{$db1}{$item_class}{$name};
                my $two = $itemhash->{$db2}{$item_class}{$name};

                for my $col (keys %$one) {

                    ## Skip if this col is ignored
                    next if exists $ignore->{$col};

                    ## If it doesn't exist on the other, just ignore it
                    next if ! exists $two->{$col};

                    ## If they are the same, move on!
                    next if $one->{$col} eq $two->{$col};

                    ## Skip certain known numeric fields that have text versions:
                    next if $col =~ /.(?:namespace|owner|filenode|oid|relid)$/;

                    ## If not a list, just report on the exact match here and move on:
                    if (! exists $lists->{$col} and $col !~ /.acl$/) {
                        $nomatch{$name}{coldiff}{$col}{$db1} = $one->{$col};
                        $nomatch{$name}{coldiff}{$col}{$db2} = $two->{$col};
                        next;
                    }

                    ## This is a list, so we have to break it down to see if it is really different
                    ## May be empty or of the form {foo=bar,baz=yak}

                    my (%list1,%list2);
                    my ($uno,$dos) = ($one->{$col}, $two->{$col});

                    if (length $uno) {
                        die "Invalid list: $uno for db $db1:$name:$col\n" if $uno !~ /^{(.+)}$/;
                        my $t = $1;
                        my @tlist = ();
                        push(@tlist, $+) while $t =~ m{"([^\"\\]*(?:\\.[^\"\\]*)*)",?
                                                 | ([^,]+),?
                                                 | ,
                                                }gx;
                        push(@tlist, undef) if substr($t, -1,1) eq ',';
                        %list1 = map { /(.*)=(.+)/ or die "Invalid list: $uno"; $1,$2 } @tlist;
                    }
                    if (length $dos) {
                        die "Invalid list: $dos for db $db2:$name:$col\n" if $dos !~ /^{(.+)}$/;
                        my $t = $1;
                        my @tlist = ();
                        push(@tlist, $+) while $t =~ m{"([^\"\\]*(?:\\.[^\"\\]*)*)",?
                                                 | ([^,]+),?
                                                 | ,
                                                }gx;
                        push(@tlist, undef) if substr($t, -1,1) eq ',';
                        %list2 = map { /(.*)=(.+)/ or die "Invalid list: $uno"; $1,$2 } @tlist;
                    }

                    ## Items in 1 but not 2?
                    for my $setting (sort keys %list1) {
                        if (! exists $list2{$setting}) {
                            $nomatch{$name}{list}{$col}{exists}{$setting}{isthere}{$db1} = 1;
                            $nomatch{$name}{list}{$col}{exists}{$setting}{nothere}{$db2} = 1;
                        }
                    }

                    ## Items in 2 but not 1? Value diferences?
                    for my $setting (sort keys %list2) {
                        if (! exists $list1{$setting}) {
                            $nomatch{$name}{list}{$col}{exists}{$setting}{isthere}{$db2} = 1;
                            $nomatch{$name}{list}{$col}{exists}{$setting}{nothere}{$db1} = 1;
                        }
                        elsif ($list1{$setting} ne $list2{$setting}) {
                            $nomatch{$name}{list}{$col}{diff}{$setting}{$db1} = $list1{$setting};
                            $nomatch{$name}{list}{$col}{diff}{$setting}{$db2} = $list2{$setting};
                        }
                    }
                }
            }
        }
    }

    $opt{failcount} += keys %nomatch;

    return \%nomatch;

} ## end of schema_item_differences


sub find_catalog_info {

    ## Grab information from one or more catalog tables
    ## Convert into a happy hashref and return it
    ## Arguments: three
    ## 1. Type of object
    ## 2. Database number
    ## 3. Version information for the database
    ## Returns: large hashref of information

    ## What type of catalog object this is
    my $type = shift;

    ## We must know about this type
    if (! exists $catalog_info{$type}) {
        die "Unknown type of '$type' sent to find_catalog_info";
    }
    my $ci = $catalog_info{$type};

    ## The final hashref of rows we return
    my $result = {};

    ## Do nothing if we are excluding this type of object entirely
    return $result if $opt{filtered}{"no$type"};

    ## Which database to run this against
    my $dbnum = shift or die;

    ## The version information
    my $dbver = shift or die;

    ## The SQL we use
    my $SQL = $ci->{SQL} or die "No SQL found for type '$type'\n";

    ## Switch to alternate SQL for different versions
    if ($type eq 'language') {
        if (int $dbver->{major} <= 8.2) {
            $SQL = $ci->{SQL2};
        }
    }

    if (exists $ci->{exclude}) {
        if ('temp_schemas' eq $ci->{exclude}) {
            if (! $opt{filtered}{system}) {
                $SQL .= q{ WHERE nspname !~ '^pg_t'};
            }
        }
        elsif ('system' eq $ci->{exclude}) {
            if (! $opt{filtered}{system}) {
                $SQL .= sprintf
                    q{ %s n.nspname !~ '^pg' AND n.nspname <> 'information_schema'},
                        $SQL =~ /WHERE/ ? 'AND' : 'WHERE';
            }
        }
        else {
            die "Unknown exclude '$ci->{exclude}' called";
        }
    }

    ## Final wrapup
    if (exists $ci->{postSQL}) {
        $SQL .= " $ci->{postSQL}";
    }

    ## Send our SQL to the correct database via psql and grab the results
    my $info = run_command($SQL, { dbnumber => $dbnum });

    ## The row column we use as the main hash key
    my $key = $ci->{keyname} || 'name';

    ## Keep track of the actual column numbers
    my $last_table = '';
    my $colnum = 1;

    ## Only need to pull back the first and only db, so we can say [0] here
  ROW:
    for my $row (@{$info->{db}[0]{slurp}}) {

        ## Remove any information that should be deleted
        for ( @{$info->{deletecols}}) {
            delete $row->{$_};
        }

        ## Determine the name to use. For most things this is simply the passed in key
        my $name = $row->{$key};

        ## For a function, we also want to put the args into the name
        if ($type eq 'function') {
            ## Once per database, grab all mappings
            if (! exists $opt{oid2type}{$dbnum}) {
                $SQL = 'SELECT oid, typname FROM pg_type';
                my $tinfo = run_command($SQL, { dbnumber => $dbnum });
                for my $row (@{ $tinfo->{db}[0]{slurp} }) {
                    $opt{oid2type}{$dbnum}{$row->{oid}} = $row->{typname};
                }
            }
            (my $args = $row->{proargtypes}) =~ s/(\d+)/$opt{oid2type}{$dbnum}{$1}||$1/ge;
            $args =~ s/ /,/g;
            $args =~ s/ints/smallint/g;
            $args =~ s/int4/int/g;
            $args =~ s/int8/bigint/g;
            $name .= "($args)";

        }

        ## For columns, reduce the attnum to a simpler canonical form without holes
        if ($type eq 'column') {
            if ($row->{tname} ne $last_table) {
                $last_table = $row->{tname};
                $colnum = 1;
            }
            $row->{column_number} = $colnum++;
        }

        ## Store this row into our result hash, using a good key
        $result->{$name} = $row;

        ## We may want to run additional SQL per row returned
        if (exists $ci->{innerSQL}) {

            if ($type eq 'sequence') {
                ## If this is a sequence, we want to grab them all at once to reduce 
                ## the amount of round-trips we do with 'SELECT * FROM seqname'
                if (! exists $opt{seqinfoss}{$dbnum}) {
                    $SQL = q{SELECT quote_ident(nspname)||'.'||quote_ident(relname) AS sname }
                         . q{FROM pg_class }
                         . q{JOIN pg_namespace n ON (n.oid = relnamespace) }
                         . q{WHERE relkind = 'S'};
                    my $sinfo = run_command($SQL, { dbnumber => $dbnum } );
                    $SQL = join "\n  UNION ALL\n" =>
                        map { "SELECT '$_->{sname}' AS fullname, * FROM $_->{sname}" }
                            @{ $sinfo->{db}[0]{slurp}};
                    $sinfo = run_command($SQL, { dbnumber => $dbnum } );

                    ## Store it back into the global hash
                    for my $row (@{ $sinfo->{db}[0]{slurp} }) {
                        $opt{seqinfoss}{$dbnum}{$row->{fullname}} = $row;
                    }
                }

                ## If it does not exist in the cache, just fall through and do it manually!
                if (exists $opt{seqinfoss}{$dbnum}{$row->{safename}}) {
                    $result->{$row->{safename}} = $opt{seqinfoss}{$dbnum}{$row->{safename}};
                    next ROW;
                }
            }

            (my $SQL2 = $ci->{innerSQL}) =~ s/ROW(\w+)/$row->{lc $1}/g;
            my $info2 = run_command($SQL2, { dbnumber => $dbnum } );
            for my $row2 (@{ $info2->{db}[0]{slurp} }) {
                for my $inner (keys %{ $row2 }) {
                    $result->{$name}{$inner} = $row2->{$inner};
                }
            }
        }
    }

    return $result;

} ## end of find_catalog_info


sub check_sequence {

    ## Checks how many values are left in sequences
    ## Supports: Nagios, MRTG
    ## Warning and critical are percentages
    ## Can exclude and include sequences

    my ($warning, $critical) = validate_range
        ({
          type              => 'percent',
          default_warning   => '85%',
          default_critical  => '95%',
          forcemrtg         => 1,
    });

    (my $w = $warning) =~ s/\D//;
    (my $c = $critical) =~ s/\D//;

    ## Gather up all sequence names
    ## no critic
    my $SQL = q{
SELECT DISTINCT ON (nspname, seqname) nspname, seqname,
  quote_ident(nspname) || '.' || quote_ident(seqname) AS safename, typname
  -- sequences by column dependency
FROM (
 SELECT depnsp.nspname, dep.relname as seqname, typname
 FROM pg_depend
 JOIN pg_class on classid = pg_class.oid
 JOIN pg_class dep on dep.oid = objid
 JOIN pg_namespace depnsp on depnsp.oid= dep.relnamespace
 JOIN pg_class refclass on refclass.oid = refclassid
 JOIN pg_class ref on ref.oid = refobjid
 JOIN pg_namespace refnsp on refnsp.oid = ref.relnamespace
 JOIN pg_attribute refattr ON (refobjid, refobjsubid) = (refattr.attrelid, refattr.attnum)
 JOIN pg_type ON refattr.atttypid = pg_type.oid
 WHERE pg_class.relname = 'pg_class'
 AND refclass.relname = 'pg_class'
 AND dep.relkind in ('S')
 AND ref.relkind in ('r')
 AND typname IN ('int2', 'int4', 'int8')
 UNION ALL
 --sequences by parsing DEFAULT constraints
 SELECT nspname, seq.relname, typname
 FROM pg_attrdef
 JOIN pg_attribute ON (attrelid, attnum) = (adrelid, adnum)
 JOIN pg_type on pg_type.oid = atttypid
 JOIN pg_class rel ON rel.oid = attrelid
 JOIN pg_class seq ON seq.relname = regexp_replace(adsrc, $re$^nextval\('(.+?)'::regclass\)$$re$, $$\1$$)
 AND seq.relnamespace = rel.relnamespace
 JOIN pg_namespace nsp ON nsp.oid = seq.relnamespace
 WHERE adsrc ~ 'nextval' AND seq.relkind = 'S' AND typname IN ('int2', 'int4', 'int8')
 UNION ALL
 -- all sequences, to catch those whose associations are not obviously recorded in pg_catalog
 SELECT nspname, relname, CAST('int8' AS TEXT)
 FROM pg_class
 JOIN pg_namespace nsp ON nsp.oid = relnamespace
 WHERE relkind = 'S'
) AS seqs
WHERE nspname !~ '^pg_temp.*'
ORDER BY nspname, seqname, typname
};
    ## use critic

    my $info = run_command($SQL, {regex => qr{\w}, emptyok => 1} );

    my $MAXINT2 = 32767;
    my $MAXINT4 = 2147483647;
    my $MAXINT8 = 9223372036854775807;

    my $limit = 0;

    for $db (@{$info->{db}}) {
        my (@crit,@warn,@ok);
        my $maxp = 0;
        my %seqinfo;
        my %seqperf;
        my $multidb = @{$info->{db}} > 1 ? "$db->{dbname}." : '';
        my @seq_sql;
        for my $r (@{$db->{slurp}}) { # for each sequence, create SQL command to inspect it
            my ($schema, $seq, $seqname, $typename) = @$r{qw/ nspname seqname safename typname /};
            next if skip_item($seq);
            my $maxValue = $typename eq 'int2' ? $MAXINT2 : $typename eq 'int4' ? $MAXINT4 : $MAXINT8;
            my $seqname_l = $seqname;
            $seqname_l =~ s/'/''/g; # SQL literal quoting (name is already identifier-quoted)
            push @seq_sql, qq{
SELECT '$seqname_l' AS seqname, last_value, slots, used, ROUND(used/slots*100) AS percent,
  CASE WHEN slots < used THEN 0 ELSE slots - used END AS numleft
FROM (
 SELECT last_value,
  CEIL((LEAST(max_value, $maxValue)-min_value::numeric+1)/increment_by::NUMERIC) AS slots,
  CEIL((last_value-min_value::numeric+1)/increment_by::NUMERIC) AS used
FROM $seqname) foo
};
        }
        # Use UNION ALL to query multiple sequences at once, however if there are too many sequences this can exceed
        # maximum argument length; so split into chunks of 200 sequences or less and iterate over them.
        while (my @seq_sql_chunk = splice @seq_sql, 0, 200) {
            my $seqinfo = run_command(join("\nUNION ALL\n", @seq_sql_chunk), { target => $db }); # execute all SQL commands at once
            for my $r2 (@{$seqinfo->{db}[0]{slurp}}) { # now look at all results
                my ($seqname, $last, $slots, $used, $percent, $left) = @$r2{qw/ seqname last_value slots used percent numleft / };
                if (! defined $last) {
                    ndie msg('seq-die', $seqname);
                }
                my $msg = msg('seq-msg', $seqname, $percent, $left);
                my $nicename = perfname("$multidb$seqname");
                $seqperf{$percent}{$seqname} = [$left, " $nicename=$percent%;$w%;$c%"];
                if ($percent >= $maxp) {
                    $maxp = $percent;
                    if (! exists $opt{perflimit} or $limit++ < $opt{perflimit}) {
                        push @{$seqinfo{$percent}} => $MRTG ? [$seqname,$percent,$slots,$used,$left] : $msg;
                    }
                }
                next if $MRTG;

                if (length $critical and $percent >= $c) {
                    push @crit => $msg;
                }
                elsif (length $warning and $percent >= $w) {
                    push @warn => $msg;
                }
            }
        }
        if ($MRTG) {
            my $msg = join ' | ' => map { $_->[0] } @{$seqinfo{$maxp}};
            do_mrtg({one => $maxp, msg => $msg});
        }
        $limit = 0;
        PERF: for my $val (sort { $b <=> $a } keys %seqperf) {
            for my $seq (sort { $seqperf{$val}{$a}->[0] <=> $seqperf{$val}{$b}->[0] or $a cmp $b } keys %{$seqperf{$val}}) {
                last PERF if exists $opt{perflimit} and $limit++ >= $opt{perflimit};
                $db->{perf} .= $seqperf{$val}{$seq}->[1];
            }
        }

        if (@crit) {
            add_critical join ' ' => @crit;
        }
        elsif (@warn) {
            add_warning join ' ' => @warn;
        }
        else {
            if (keys %seqinfo) {
                add_ok join ' ' => @{$seqinfo{$maxp}};
            }
            else {
                add_ok msg('seq-none');
            }
        }
    }

    return;

} ## end of check_sequence


sub check_settings_checksum {

    ## Verify the checksum of all settings
    ## Supports: Nagios, MRTG
    ## Not that this will vary from user to user due to ALTER USER
    ## and because superusers see additional settings
    ## One of warning or critical must be given (but not both)
    ## It should run one time to find out the expected checksum
    ## You can use --critical="0" to find out the checksum
    ## You can include or exclude settings as well
    ## Example:
    ##  check_postgres_settings_checksum --critical="4e7ba68eb88915d3d1a36b2009da4acd"

    my ($warning, $critical) = validate_range({type => 'checksum', onlyone => 1});

    eval {
        require Digest::MD5;
    };
    if ($@) {
        ndie msg('checksum-nomd');
    }

    $SQL = 'SELECT name, setting FROM pg_settings ORDER BY name';
    my $info = run_command($SQL, { regex => qr[client_encoding] });

    for $db (@{$info->{db}}) {

        my $newstring = '';
        for my $r (@{$db->{slurp}}) {
            next SLURP if skip_item($r->{name});
            $newstring .= "$r->{name} $r->{setting}\n";
        }
        if (! length $newstring) {
            add_unknown msg('no-match-set');
        }

        my $checksum = Digest::MD5::md5_hex($newstring);

        my $msg = msg('checksum-msg', $checksum);
        if ($MRTG) {
            $opt{mrtg} or ndie msg('checksum-nomrtg');
            do_mrtg({one => $opt{mrtg} eq $checksum ? 1 : 0, msg => $checksum});
        }
        if ($critical and $critical ne $checksum) {
            add_critical $msg;
        }
        elsif ($warning and $warning ne $checksum) {
            add_warning $msg;
        }
        elsif (!$critical and !$warning) {
            add_unknown $msg;
        }
        else {
            add_ok $msg;
        }
    }

    return;

} ## end of check_settings_checksum


sub check_slony_status {

    ## Checks the sl_status table
    ## Returns unknown if sl_status is not found
    ## Returns critical is status is not "good"
    ## Otherwise, returns based on time-based warning and critical options
    ## Supports: Nagios, MRTG

    my ($warning, $critical) = validate_range
        ({
          type              => 'time',
          default_warning   => '60',
          default_critical  => '300',
        });

    ## If given schemas on the command-line, map back to targetdbs
    if (defined $opt{schema}) {
        my $x = 0;
        for my $db (@targetdb) {
            $db->{schemalist} = $opt{schema}->[$x] || '';
            $x++;
        }
    }
    else {
        ## Otherwise, find all slony schemas and put them in ourselves
        $SQL = q{SELECT quote_ident(nspname) AS nspname FROM pg_namespace WHERE oid IN }.
        q{(SELECT relnamespace FROM pg_class WHERE relkind = 'v' AND relname = 'sl_status')};
        my $info = run_command($SQL);
        for my $db (@{ $info->{db} }) {
            $db->{schemalist} = join ',' => map { $_->{nspname} } @{ $db->{slurp} };
        }
    }

    my $SLSQL =
q{SELECT
 ROUND(EXTRACT(epoch FROM st_lag_time)) AS lagtime,
 st_origin,
 st_received,
 current_database() AS cd,
 COALESCE(n1.no_comment, '') AS com1,
 COALESCE(n2.no_comment, '') AS com2
FROM SCHEMA.sl_status
JOIN SCHEMA.sl_node n1 ON (n1.no_id=st_origin)
JOIN SCHEMA.sl_node n2 ON (n2.no_id=st_received)
ORDER BY 1 DESC};

    my $maxlagtime = -1;

    my $x = 1;
    for $db (@targetdb) {
        next if ! $db->{schemalist};
        $db->{perf} = '';
        my @perf;
        for my $schema (split /,/ => $db->{schemalist}) {
            ## Set for output
            $db->{showschema} = $schema;

            (my $SQL = $SLSQL) =~ s/SCHEMA/$schema/g;
            my $info = run_command($SQL, { dbnumber => $x });
            my $slurp = $info->{db}[0]{slurp}[0];
            if (! defined $slurp->{lagtime}) {
                add_unknown msg('slony-nonumber');
                return;
            }
            my ($lag,$from,$to,$dbname,$fromc,$toc) = @$slurp{qw/ lagtime st_origin st_received cd com1 com2/};
            $maxlagtime = $lag if $lag > $maxlagtime;
            push @perf => [
                $lag,
                $from,
                qq{'$dbname.$schema Node $from($fromc) -> Node $to($toc)'=$lag;$warning;$critical},
            ];

        } ## end each schema in this database

        if ($MRTG) {
            do_mrtg({one => $maxlagtime});
            return;
        }

        $db->{perf} .= join "\n" => map { $_->[2] } sort { $b->[0]<=>$a->[0] or $a->[1] cmp $b->[1] } @perf;

        my $msg = msg('slony-lagtime', $maxlagtime);
        $msg .= sprintf ' (%s)', pretty_time($maxlagtime, $maxlagtime > 500 ? 'S' : '');
        if (length $critical and $maxlagtime >= $critical) {
            add_critical $msg;
        }
        elsif (length $warning and $maxlagtime >= $warning) {
            add_warning $msg;
        }
        else {
            add_ok $msg;
        }

        $x++;
    }

    if ($maxlagtime < 1) { ## No schemas found
        add_unknown msg('slony-noschema');
    }

    return;

} ## end of check_slony_status


sub check_timesync {

    ## Compare local time to the database time
    ## Supports: Nagios, MRTG
    ## Warning and critical are given in number of seconds difference

    my ($warning,$critical) = validate_range
        ({
          type             => 'seconds',
          default_warning  => 2,
          default_critical => 5,
          });

    $SQL = q{SELECT round(extract(epoch FROM now())) AS epok, TO_CHAR(now(),'YYYY-MM-DD HH24:MI:SS') AS pretti};
    my $info = run_command($SQL);
    my $localepoch = time;
    my @l = localtime;

    for $db (@{$info->{db}}) {
        my ($pgepoch,$pgpretty) = @{$db->{slurp}->[0]}{qw/ epok pretti /};

        my $diff = abs($pgepoch - $localepoch);
        if ($MRTG) {
            do_mrtg({one => $diff, msg => "DB: $db->{dbname}"});
        }
        $db->{perf} = sprintf '%s=%ss;%s;%s',
            perfname(msg('timesync-diff')), $diff, $warning, $critical;

        my $localpretty = sprintf '%d-%02d-%02d %02d:%02d:%02d', $l[5]+1900, $l[4]+1, $l[3],$l[2],$l[1],$l[0];
        my $msg = msg('timesync-msg', $diff, $pgpretty, $localpretty);

        if (length $critical and $diff >= $critical) {
            add_critical $msg;
        }
        elsif (length $warning and $diff >= $warning) {
            add_warning $msg;
        }
        else {
            add_ok $msg;
        }
    }
    return;

} ## end of check_timesync


sub check_txn_idle {

    ## Check the duration and optionally number of "idle in transaction" processes
    ## Supports: Nagios, MRTG
    ## It makes no sense to run this more than once on the same cluster
    ## Warning and critical are time limits or counts for time limits - default to seconds
    ## Valid time units: s[econd], m[inute], h[our], d[ay]
    ## All above may be written as plural as well (e.g. "2 hours")
    ## Valid counts for time limits: "$int for $time"
    ## Can also ignore databases with exclude and limit with include
    ## Limit to a specific user with the includeuser option
    ## Exclude users with the excludeuser option

    my $type = shift || 'txnidle';
    my $thing = shift || msg('transactions');
    my $perf  = shift || msg('txn-time');
    my $start = shift || 'query_start';
    my $clause = shift || q{current_query ~ '^<'};

    ## Extract the warning and critical seconds and counts.
    ## If not given, items will be an empty string
    my ($wcount, $wtime, $ccount, $ctime) = validate_integer_for_time();

    ## We don't GROUP BY because we want details on every connection
    ## Someday we may even break things down by database
    my ($SQL2, $SQL3);
    if ($type ne 'qtime') {
        $SQL = q{SELECT datname, datid, procpid AS pid, usename, client_addr, xact_start, current_query AS current_query, '' AS state, }.
            q{CASE WHEN client_port < 0 THEN 0 ELSE client_port END AS client_port, }.
            qq{COALESCE(ROUND(EXTRACT(epoch FROM now()-$start)),0) AS seconds }.
            qq{FROM pg_stat_activity WHERE ($clause)$USERWHERECLAUSE }.
            q{ORDER BY xact_start, query_start, procpid DESC};
        ## Craft an alternate version for old servers that do not have the xact_start column:
        ($SQL2 = $SQL) =~ s/xact_start/query_start AS xact_start/;
        $SQL2 =~ s/BY xact_start,/BY/;
    }
    else {
        $SQL2 = $SQL = q{SELECT datname, datid, procpid AS pid, usename, client_addr, current_query AS current_query, '' AS state, }.
            q{CASE WHEN client_port < 0 THEN 0 ELSE client_port END AS client_port, }.
            qq{COALESCE(ROUND(EXTRACT(epoch FROM now()-$start)),0) AS seconds }.
            qq{FROM pg_stat_activity WHERE ($clause)$USERWHERECLAUSE }.
            q{ORDER BY query_start, procpid DESC};
    }

    ## Craft an alternate version for new servers which do not have procpid and current_query is split
    ($SQL3 = $SQL) =~ s/procpid/pid/g;
    $SQL3 =~ s/current_query ~ '\^<'/(state = 'idle in transaction' OR state IS NULL)/;
    $SQL3 =~ s/current_query NOT LIKE '<IDLE>%'/(state NOT LIKE 'idle%' OR state IS NULL)/; # query_time
    $SQL3 =~ s/current_query/query/g;
    $SQL3 =~ s/'' AS state/state AS state/;

    my $info = run_command($SQL, { emptyok => 1 , version => [ "<8.3 $SQL2", ">9.1 $SQL3" ] } );

    ## Extract the first entry
    $db = $info->{db}[0];

    ## Store the current longest row
    my $maxr = { seconds => 0 };

    ## How many valid rows did we get?
    my $count = 0;

    ## Info about the top offender
    my $whodunit = '';
    if ($MRTG) {
        if (defined $db->{dbname}) {
            $whodunit = "DB: $db->{dbname}";
        } else {
            $whodunit = sprintf q{DB: %s}, msg('no-db');
        }
    }

    ## Process each returned row
    for my $r (@{ $db->{slurp} }) {

        ## Skip if we don't care about this database
        next if skip_item($r->{datname});

        ## We do a lot of filtering based on the current_query or state in 9.2+
        my $cq = $r->{query} || $r->{current_query};
        my $st = $r->{state} || '';

        ## Return unknown if we cannot see because we are a non-superuser
        if ($cq =~ /insufficient/o) {
            add_unknown msg('psa-nosuper');
            return;
        }

        ## Return unknown if stats_command_string / track_activities is off
        if ($cq =~ /disabled/o or $cq =~ /<command string not enabled>/) {
            add_unknown msg('psa-disabled');
            return;
        }

        ## Detect other cases where pg_stat_activity is not fully populated
        if ($type ne 'qtime' and length $r->{xact_start} and $r->{xact_start} !~ /\d/o) {
            add_unknown msg('psa-noexact');
            return;
        }

        ## Filter out based on the action
        next if $action eq 'txn_idle' and $cq ne '<IDLE> in transaction' and $st ne 'idle in transaction';

        ## Keep track of the longest overall time
        $maxr = $r if $r->{seconds} >= $maxr->{seconds};

        $count++;
    }

    ## If there were no matches, then there were no rows, or no non-excluded rows
    ## We don't care which at the moment, and return the same message
    if (! $count) {
        $MRTG and do_mrtg({one => 0, msg => $whodunit});
        $db->{perf} = "$perf=0;$wtime;$ctime";

        add_ok msg("$type-none");
        return;
    }

    ## Extract the seconds to avoid typing out the hash each time
    my $max = $maxr->{seconds};

    ## See if we have a minimum number of matches
    my $base_count = $wcount || $ccount;
    if ($base_count and $count < $base_count) {
        $db->{perf} = "$perf=$count;$wcount;$ccount";
        add_ok msg("$type-count-none", $base_count);
        return;
    }

    ## Details on who the top offender was
    if ($max > 0) {
        $whodunit = sprintf q{%s:%s %s:%s %s:%s%s%s %s:%s},
            msg('PID'), $maxr->{pid},
            msg('database'), $maxr->{datname},
            msg('username'), $maxr->{usename},
            $maxr->{client_addr} eq '' ? '' : (sprintf ' %s:%s', msg('address'), $maxr->{client_addr}),
            ($maxr->{client_port} eq '' or $maxr->{client_port} < 1)
                ? '' : (sprintf ' %s:%s', msg('port'), $maxr->{client_port}),
            msg('query'),  $maxr->{query} || $maxr->{current_query};
    }

    ## For MRTG, we can simply exit right now
    if ($MRTG) {
        do_mrtg({one => $max, msg => $whodunit});
        exit;
    }

    ## If the number of seconds is high, show an alternate form
    my $ptime = $max > 300 ? ' (' . pretty_time($max) . ')' : '';

    ## Show the maximum number of seconds in the perf section
    $db->{perf} .= sprintf q{%s=%ss;%s;%s},
        $perf,
        $max,
        $wtime,
        $ctime;

    if (length $ctime and length $ccount) {
        if ($max >= $ctime and $count >= $ccount) {
            add_critical msg("$type-for-msg", $count, $ctime, $max, $ptime, $whodunit);
            return;
        }
    }
    elsif (length $ctime) {
        if ($max >= $ctime) {
            add_critical msg("$type-msg", $max, $ptime, $whodunit);
            return;
        }
    }
    elsif (length $ccount) {
        if ($count >= $ccount) {
            add_critical msg("$type-count-msg", $count);
            return;
        }
    }

    if (length $wtime and length $wcount) {
        if ($max >= $wtime and $count >= $wcount) {
            add_warning msg("$type-for-msg", $count, $wtime, $max, $ptime, $whodunit);
            return;
        }
    }
    elsif (length $wtime) {
        if ($max >= $wtime) {
            add_warning msg("$type-msg", $max, $ptime, $whodunit);
            return;
        }
    }
    elsif (length $wcount) {
        if ($count >= $wcount) {
            add_warning msg("$type-count-msg", $count);
            return;
        }
    }

    add_ok msg("$type-msg", $max, $ptime, $whodunit);

    return;

} ## end of check_txn_idle


sub check_txn_time {

    ## This is the same as check_txn_idle, but we want where the 
    ## transaction start time is not null

    check_txn_idle('txntime',
                   '',
                   '',
                   'xact_start',
                   q{xact_start IS NOT NULL});

    return;

} ## end of check_txn_time


sub check_txn_wraparound {

    ## Check how close to transaction wraparound we are on all databases
    ## Supports: Nagios, MRTG
    ## Warning and critical are the number of transactions performed
    ## Thus, anything *over* that number will trip the alert
    ## See: http://www.postgresql.org/docs/current/static/routine-vacuuming.html#VACUUM-FOR-WRAPAROUND
    ## It makes no sense to run this more than once on the same cluster

    my ($warning, $critical) = validate_range
        ({
          type             => 'positive integer',
          default_warning  => 1_300_000_000,
          default_critical => 1_400_000_000,
          });

    if ($warning and $warning >= 2_000_000_000) {
        ndie msg('txnwrap-wbig');
    }
    if ($critical and $critical >= 2_000_000_000) {
        ndie msg('txnwrap-cbig');
    }

    $SQL = q{SELECT datname, age(datfrozenxid) AS age FROM pg_database WHERE datallowconn ORDER BY 1, 2};
    my $info = run_command($SQL, { regex => qr[\w+\s+\|\s+\d+] } );

    my ($mrtgmax,$mrtgmsg) = (0,'?');
    for $db (@{$info->{db}}) {
        my ($max,$msg) = (0,'?');
        for my $r (@{$db->{slurp}}) {
            my ($dbname,$dbtxns) = ($r->{datname},$r->{age});
            $db->{perf} .= sprintf ' %s=%s;%s;%s;%s;%s',
                perfname($dbname), $dbtxns, $warning, $critical, 0, 2000000000;
            next SLURP if skip_item($dbname);
            if ($dbtxns > $max) {
                $max = $dbtxns;
                $msg = qq{$dbname: $dbtxns};
                if ($dbtxns > $mrtgmax) {
                    $mrtgmax = $dbtxns;
                    $mrtgmsg = "DB: $dbname";
                }
            }
        }
        if (length $critical and $max >= $critical) {
            add_critical $msg;
        }
        elsif (length $warning and $max >= $warning) {
            add_warning $msg;
        }
        else {
            add_ok $msg;
        }
    }
    $MRTG and do_mrtg({one => $mrtgmax, msg => $mrtgmsg});

    return;

} ## end of check_txn_wraparound


sub check_version {

    ## Compare version with what we think it should be
    ## Supports: Nagios, MRTG
    ## Warning and critical are the major and minor (e.g. 8.3)
    ## or the major, minor, and revision (e.g. 8.2.4 or even 8.3beta4)

    if ($MRTG) {
        if (!exists $opt{mrtg} or $opt{mrtg} !~ /^\d+\.\d+/) {
            ndie msg('version-badmrtg');
        }
        if ($opt{mrtg} =~ /^\d+\.\d+$/) {
            $opt{critical} = $opt{mrtg};
        }
        else {
            $opt{warning} = $opt{mrtg};
        }
    }

    my ($warning, $critical) = validate_range({type => 'version', forcemrtg => 1});

    my ($warnfull, $critfull) = (($warning =~ /^\d+\.\d+$/ ? 0 : 1),($critical =~ /^\d+\.\d+$/ ? 0 : 1));

    my $info = run_command('SELECT version() AS version');

    for $db (@{$info->{db}}) {
        my $row = $db->{slurp}[0];
        if ($row->{version} !~ /((\d+\.\d+)(\w+|\.\d+))/o) {
            add_unknown msg('invalid-query', $row->{version});
            next;
        }
        my ($full,$version,$revision) = ($1,$2,$3||'?');
        $revision =~ s/^\.//;

        my $ok = 1;

        if (length $critical) {
            if (($critfull and $critical ne $full)
                or (!$critfull and $critical ne $version)) {
                $MRTG and do_mrtg({one => 0, msg => $full});
                add_critical msg('version-fail', $full, $critical);
                $ok = 0;
            }
        }
        elsif (length $warning) {
            if (($warnfull and $warning ne $full)
                or (!$warnfull and $warning ne $version)) {
                $MRTG and do_mrtg({one => 0, msg => $full});
                add_warning msg('version-fail', $full, $warning);
                $ok = 0;
            }
        }
        if ($ok) {
            $MRTG and do_mrtg({one => 1, msg => $full});
            add_ok msg('version-ok', $full);
        }
    }

    return;

} ## end of check_version


sub check_wal_files {

    ## Check on the number of WAL, or WAL "ready", files in use
    ## Supports: Nagios, MRTG
    ## Must run as a superuser
    ## Critical and warning are the number of files
    ## Example: --critical=40

    my $subdir = shift || '';
    my $extrabit = shift || '';

    my $default_warning = shift || 10;
    my $default_critical = shift || 15;

    my $arg = {type => 'positive integer', leastone => 1};
    if ($default_warning) {
        $arg->{default_warning} = $default_warning;
    }
    if ($default_critical) {
        $arg->{default_critical} = $default_critical;
    }

    my ($warning, $critical) = validate_range($arg);

    ## Figure out where the pg_xlog directory is
    $SQL = qq{SELECT count(*) AS count FROM pg_ls_dir('pg_xlog$subdir') WHERE pg_ls_dir ~ E'^[0-9A-F]{24}$extrabit\$'}; ## no critic (RequireInterpolationOfMetachars)

    my $info = run_command($SQL, {regex => qr[\d] });

    my $found = 0;
    for $db (@{$info->{db}}) {
        my $r = $db->{slurp}[0];
        my $numfiles = $r->{count};
        if ($MRTG) {
            do_mrtg({one => $numfiles});
        }
        my $msg = $extrabit ? msg('wal-numfound2', $numfiles, $extrabit)
            : msg('wal-numfound', $numfiles);
        $db->{perf} .= sprintf '%s=%s;%s;%s',
            perfname(msg('files')), $numfiles, $warning, $critical;
        if (length $critical and $numfiles > $critical) {
            add_critical $msg;
        }
        elsif (length $warning and $numfiles > $warning) {
            add_warning $msg;
        }
        else {
            add_ok $msg;
        }
    }

    return;

} ## end of check_wal_files

=pod

=encoding utf8

=head1 NAME

B<check_postgres.pl> - a Postgres monitoring script for Nagios, MRTG, Cacti, and others

This documents describes check_postgres.pl version 2.22.0

=head1 SYNOPSIS

  ## Create all symlinks
  check_postgres.pl --symlinks

  ## Check connection to Postgres database 'pluto':
  check_postgres.pl --action=connection --db=pluto

  ## Same things, but using the symlink
  check_postgres_connection --db=pluto

  ## Warn if > 100 locks, critical if > 200, or > 20 exclusive
  check_postgres_locks --warning=100 --critical="total=200:exclusive=20"

  ## Show the current number of idle connections on port 6543:
  check_postgres_txn_idle --port=6543 --output=simple

  ## There are many other actions and options, please keep reading.

  The latest news and documentation can always be found at:
  http://bucardo.org/check_postgres/

=head1 DESCRIPTION

check_postgres.pl is a Perl script that runs many different tests against 
one or more Postgres databases. It uses the psql program to gather the 
information, and outputs the results in one of three formats: Nagios, MRTG, 
or simple.

=head2 Output Modes

The output can be changed by use of the C<--output> option. The default output 
is nagios, although this can be changed at the top of the script if you wish. The 
current option choices are B<nagios>, B<mrtg>, and B<simple>. To avoid having to 
enter the output argument each time, the type of output is automatically set 
if no --output argument is given, and if the current directory has one of the 
output options in its name. For example, creating a directory named mrtg and 
populating it with symlinks via the I<--symlinks> argument would ensure that 
any actions run from that directory will always default to an output of "mrtg"
As a shortcut for --output=simple, you can enter --simple, which also overrides 
the directory naming trick.


=head3 Nagios output

The default output format is for Nagios, which is a single line of information, along 
with four specific exit codes:

=over 2

=item 0 (OK)

=item 1 (WARNING)

=item 2 (CRITICAL)

=item 3 (UNKNOWN)

=back

The output line is one of the words above, a colon, and then a short description of what 
was measured. Additional statistics information, as well as the total time the command 
took, can be output as well: see the documentation on the arguments 
I<L<--showperf|/--showperf=VAL>>, 
I<L<--perflimit|/--perflimit=i>>, and 
I<L<--showtime|/--showtime=VAL>>.

=head3 MRTG output

The MRTG output is four lines, with the first line always giving a single number of importance. 
When possible, this number represents an actual value such as a number of bytes, but it 
may also be a 1 or a 0 for actions that only return "true" or "false", such as check_postgres_version.
The second line is an additional stat and is only used for some actions. The third line indicates 
an "uptime" and is not used. The fourth line is a description and usually indicates the name of 
the database the stat from the first line was pulled from, but may be different depending on the 
action.

Some actions accept an optional I<--mrtg> argument to further control the output.

See the documentation on each action for details on the exact MRTG output for each one.

=head3 Simple output

The simple output is simply a truncated version of the MRTG one, and simply returns the first number 
and nothing else. This is very useful when you just want to check the state of something, regardless 
of any threshold. You can transform the numeric output by appending KB, MB, GB, TB, or EB to the output 
argument, for example:

  --output=simple,MB

=head3 Cacti output

The Cacti output consists of one or more items on the same line, with a simple name, a colon, and 
then a number. At the moment, the only action with explicit Cacti output is 'dbstats', and using 
the --output option is not needed in this case, as Cacti is the only output for this action. For many 
other actions, using --simple is enough to make Cacti happy.

=head1 DATABASE CONNECTION OPTIONS

All actions accept a common set of database options.

=over 4

=item B<-H NAME> or B<--host=NAME>

Connect to the host indicated by NAME. Can be a comma-separated list of names. Multiple host arguments 
are allowed. If no host is given, defaults to the C<PGHOST> environment variable or no host at all 
(which indicates using a local Unix socket). You may also use "--dbhost".

=item B<-p PORT> or B<--port=PORT>

Connects using the specified PORT number. Can be a comma-separated list of port numbers, and multiple 
port arguments are allowed. If no port number is given, defaults to the C<PGPORT> environment variable. If 
that is not set, it defaults to 5432. You may also use "--dbport"

=item B<-db NAME> or B<--dbname=NAME>

Specifies which database to connect to. Can be a comma-separated list of names, and multiple dbname 
arguments are allowed. If no dbname option is provided, defaults to the C<PGDATABASE> environment variable. 
If that is not set, it defaults to 'postgres' if psql is version 8 or greater, and 'template1' otherwise.

=item B<-u USERNAME> or B<--dbuser=USERNAME>

The name of the database user to connect as. Can be a comma-separated list of usernames, and multiple 
dbuser arguments are allowed. If this is not provided, it defaults to the C<PGUSER> environment variable, otherwise 
it defaults to 'postgres'.

=item B<--dbpass=PASSWORD>

Provides the password to connect to the database with. Use of this option is highly discouraged.
Instead, one should use a .pgpass or pg_service.conf file.

=item B<--dbservice=NAME>

The name of a service inside of the pg_service.conf file. Before version 9.0 of Postgres, this is 
a global file, usually found in /etc/pg_service.conf. If you are using version 9.0 or higher of 
Postgres, you can use the file ".pg_service.conf" in the home directory of the user running 
the script, e.g. nagios.

This file contains a simple list of connection options. You can also pass additional information 
when using this option such as --dbservice="maindatabase sslmode=require"

The documentation for this file can be found at
http://www.postgresql.org/docs/current/static/libpq-pgservice.html

=back

The database connection options can be grouped: I<--host=a,b --host=c --port=1234 --port=3344>
would connect to a-1234, b-1234, and c-3344. Note that once set, an option 
carries over until it is changed again.

Examples:

  --host=a,b --port=5433 --db=c
  Connects twice to port 5433, using database c, to hosts a and b: a-5433-c b-5433-c

  --host=a,b --port=5433 --db=c,d
  Connects four times: a-5433-c a-5433-d b-5433-c b-5433-d

  --host=a,b --host=foo --port=1234 --port=5433 --db=e,f
  Connects six times: a-1234-e a-1234-f b-1234-e b-1234-f foo-5433-e foo-5433-f

  --host=a,b --host=x --port=5432,5433 --dbuser=alice --dbuser=bob -db=baz
  Connects three times: a-5432-alice-baz b-5433-alice-baz x-5433-bob-baz

  --dbservice="foo" --port=5433
  Connects using the named service 'foo' in the pg_service.conf file, but overrides the port

=head1 OTHER OPTIONS

Other options include:

=over 4

=item B<--action=NAME>

States what action we are running. Required unless using a symlinked file, 
in which case the name of the file is used to figure out the action.

=item B<--warning=VAL or -w VAL>

Sets the threshold at which a warning alert is fired. The valid options for this 
option depends on the action used.

=item B<--critical=VAL or -c VAL>

Sets the threshold at which a critical alert is fired. The valid options for this 
option depends on the action used.

=item B<-t VAL> or B<--timeout=VAL>

Sets the timeout in seconds after which the script will abort whatever it is doing 
and return an UNKNOWN status. The timeout is per Postgres cluster, not for the entire 
script. The default value is 10; the units are always in seconds.

=item B<--assume-standby-mode>

If specified, first the check if server in standby mode will be performed
(--datadir is required), if so, all checks that require SQL queries will be
ignored and "Server in standby mode" with OK status will be returned instead.

Example:

    postgres@db$./check_postgres.pl --action=version --warning=8.1 --datadir /var/lib/postgresql/8.3/main/ --assume-standby-mode
    POSTGRES_VERSION OK:  Server in standby mode | time=0.00

=item B<--assume-prod>

If specified, check if server in production mode is performed (--datadir is required).
The option is only relevant for (C<symlink: check_postgres_checkpoint>).

Example:

    postgres@db$./check_postgres.pl --action=checkpoint --datadir /var/lib/postgresql/8.3/main/ --assume-prod
    POSTGRES_CHECKPOINT OK: Last checkpoint was 72 seconds ago | age=72;;300 mode=MASTER

=item B<-h> or B<--help>

Displays a help screen with a summary of all actions and options.

=item B<--man>

Displays the entire manual.

=item B<-V> or B<--version>

Shows the current version.

=item B<-v> or B<--verbose>

Set the verbosity level. Can call more than once to boost the level. Setting it to three 
or higher (in other words, issuing C<-v -v -v>) turns on debugging information for this 
program which is sent to stderr.

=item B<--showperf=VAL>

Determines if we output additional performance data in standard Nagios format 
(at end of string, after a pipe symbol, using name=value). 
VAL should be 0 or 1. The default is 1. Only takes effect if using Nagios output mode.

=item B<--perflimit=i>

Sets a limit as to how many items of interest are reported back when using the 
I<showperf> option. This only has an effect for actions that return a large 
number of items, such as B<table_size>. The default is 0, or no limit. Be 
careful when using this with the I<--include> or I<--exclude> options, as 
those restrictions are done I<after> the query has been run, and thus your 
limit may not include the items you want. Only takes effect if using Nagios output mode.

=item B<--showtime=VAL>

Determines if the time taken to run each query is shown in the output. VAL 
should be 0 or 1. The default is 1. No effect unless I<showperf> is on.
Only takes effect if using Nagios output mode.

=item B<--test>

Enables test mode. See the L</"TEST MODE"> section below.

=item B<--PGBINDIR=PATH>

Tells the script where to find the psql binaries. Useful if you have more than
one version of the PostgreSQL executables on your system, or if there are not
in your path. Note that this option is in all uppercase. By default, this option
is I<not allowed>. To enable it, you must change the C<$NO_PSQL_OPTION> near the
top of the script to 0. Avoid using this option if you can, and instead use
environment variable c<PGBINDIR> or hard-coded C<$PGBINDIR> variable, also near
the top of the script, to set the path to the PostgreSQL to use.

=item B<--PSQL=PATH>

I<(deprecated, this option may be removed in a future release!)>
Tells the script where to find the psql program. Useful if you have more than 
one version of the psql executable on your system, or if there is no psql program 
in your path. Note that this option is in all uppercase. By default, this option 
is I<not allowed>. To enable it, you must change the C<$NO_PSQL_OPTION> near the 
top of the script to 0. Avoid using this option if you can, and instead hard-code 
your psql location into the C<$PSQL> variable, also near the top of the script.

=item B<--symlinks>

Creates symlinks to the main program for each action.

=item B<--output=VAL>

Determines the format of the output, for use in various programs. The
default is 'nagios'. Available options are 'nagios', 'mrtg', 'simple'
and 'cacti'.

=item B<--mrtg=VAL>

Used only for the MRTG or simple output, for a few specific actions.

=item B<--debugoutput=VAL>

Outputs the exact string returned by psql, for use in debugging. The value is one or more letters,
which determine if the output is displayed or not, where 'a' = all, 'c' = critical, 'w' = warning,
'o' = ok, and 'u' = unknown. Letters can be combined.

=item B<--get_method=VAL>

Allows specification of the method used to fetch information for the C<new_version_cp>, 
C<new_version_pg>, C<new_version_bc>, C<new_version_box>, and C<new_version_tnm> checks. 
The following programs are tried, in order, to grab the information from the web: 
GET, wget, fetch, curl, lynx, links. To force the use of just one (and thus remove the 
overhead of trying all the others until one of those works), enter one of the names as 
the argument to get_method. For example, a BSD box might enter the following line in 
their C<.check_postgresrc> file:

  get_method=fetch

=item B<--language=VAL>

Set the language to use for all output messages. Normally, this is detected by examining 
the environment variables LC_ALL, LC_MESSAGES, and LANG, but setting this option 
will override any such detection.

=back


=head1 ACTIONS

The script runs one or more actions. This can either be done with the --action 
flag, or by using a symlink to the main file that contains the name of the action 
inside of it. For example, to run the action "timesync", you may either issue:

  check_postgres.pl --action=timesync

or use a program named:

  check_postgres_timesync

All the symlinks are created for you in the current directory 
if use the option --symlinks

  perl check_postgres.pl --symlinks

If the file name already exists, it will not be overwritten. If the file exists 
and is a symlink, you can force it to overwrite by using "--action=build_symlinks_force"

Most actions take a I<--warning> and a I<--critical> option, indicating at what 
point we change from OK to WARNING, and what point we go to CRITICAL. Note that 
because criticals are always checked first, setting the warning equal to the 
critical is an effective way to turn warnings off and always give a critical.

The current supported actions are:

=head2 B<archive_ready>

(C<symlink: check_postgres_archive_ready>) Checks how many WAL files with extension F<.ready> 
exist in the F<pg_xlog/archive_status> directory, which is found 
off of your B<data_directory>. This action must be run as a superuser, in order to access the 
contents of the F<pg_xlog/archive_status> directory. The minimum version to use this action is 
Postgres 8.1. The I<--warning> and I<--critical> options are simply the number of 
F<.ready> files in the F<pg_xlog/archive_status> directory. 
Usually, these values should be low, turning on the archive mechanism, we usually want it to 
archive WAL files as fast as possible.

If the archive command fail, number of WAL in your F<pg_xlog> directory will grow until
exhausting all the disk space and force PostgreSQL to stop immediately.

Example 1: Check that the number of ready WAL files is 10 or less on host "pluto"

  check_postgres_archive_ready --host=pluto --critical=10

For MRTG output, reports the number of ready WAL files on line 1.

=head2 B<autovac_freeze>

(C<symlink: check_postgres_autovac_freeze>) Checks how close each database is to the Postgres B<autovacuum_freeze_max_age> setting. This 
action will only work for databases version 8.2 or higher. The I<--warning> and 
I<--critical> options should be expressed as percentages. The 'age' of the transactions 
in each database is compared to the autovacuum_freeze_max_age setting (200 million by default) 
to generate a rounded percentage. The default values are B<90%> for the warning and B<95%> for 
the critical. Databases can be filtered by use of the I<--include> and I<--exclude> options. 
See the L</"BASIC FILTERING"> section for more details.

Example 1: Give a warning when any databases on port 5432 are above 97%

  check_postgres_autovac_freeze --port=5432 --warning="97%"

For MRTG output, the highest overall percentage is reported on the first line, and the highest age is 
reported on the second line. All databases which have the percentage from the first line are reported 
on the fourth line, separated by a pipe symbol.

=head2 B<backends>

(C<symlink: check_postgres_backends>) Checks the current number of connections for one or more databases, and optionally 
compares it to the maximum allowed, which is determined by the 
Postgres configuration variable B<max_connections>. The I<--warning> and 
I<--critical> options can take one of three forms. First, a simple number can be 
given, which represents the number of connections at which the alert will be 
given. This choice does not use the B<max_connections> setting. Second, the 
percentage of available connections can be given. Third, a negative number can 
be given which represents the number of connections left until B<max_connections> 
is reached. The default values for I<--warning> and I<--critical> are '90%' and '95%'.
You can also filter the databases by use of the I<--include> and I<--exclude> options.
See the L</"BASIC FILTERING"> section for more details.

To view only non-idle processes, you can use the I<--noidle> argument. Note that the 
user you are connecting as must be a superuser for this to work properly.

Example 1: Give a warning when the number of connections on host quirm reaches 120, and a critical if it reaches 150.

  check_postgres_backends --host=quirm --warning=120 --critical=150

Example 2: Give a critical when we reach 75% of our max_connections setting on hosts lancre or lancre2.

  check_postgres_backends --warning='75%' --critical='75%' --host=lancre,lancre2

Example 3: Give a warning when there are only 10 more connection slots left on host plasmid, and a critical 
when we have only 5 left.

  check_postgres_backends --warning=-10 --critical=-5 --host=plasmid

Example 4: Check all databases except those with "test" in their name, but allow ones that are named "pg_greatest". Connect as port 5432 on the first two hosts, and as port 5433 on the third one. We want to always throw a critical when we reach 30 or more connections.

 check_postgres_backends --dbhost=hong,kong --dbhost=fooey --dbport=5432 --dbport=5433 --warning=30 --critical=30 --exclude="~test" --include="pg_greatest,~prod"

For MRTG output, the number of connections is reported on the first line, and the fourth line gives the name of the database, 
plus the current maximum_connections. If more than one database has been queried, the one with the highest number of 
connections is output.

=head2 B<bloat>

(C<symlink: check_postgres_bloat>) Checks the amount of bloat in tables and indexes. (Bloat is generally the amount 
of dead unused space taken up in a table or index. This space is usually reclaimed 
by use of the VACUUM command.) This action requires that stats collection be 
enabled on the target databases, and requires that ANALYZE is run frequently. 
The I<--include> and I<--exclude> options can be used to filter out which tables 
to look at. See the L</"BASIC FILTERING"> section for more details.

The I<--warning> and I<--critical> options can be specified as sizes, percents, or both.
Valid size units are bytes, kilobytes, megabytes, gigabytes, terabytes, exabytes, 
petabytes, and zettabytes. You can abbreviate all of those with the first letter. Items 
without units are assumed to be 'bytes'. The default values are '1 GB' and '5 GB'. The value 
represents the number of "wasted bytes", or the difference between what is actually 
used by the table and index, and what we compute that it should be.

Note that this action has two hard-coded values to avoid false alarms on 
smaller relations. Tables must have at least 10 pages, and indexes at least 15, 
before they can be considered by this test. If you really want to adjust these 
values, you can look for the variables I<$MINPAGES> and I<$MINIPAGES> at the top of the 
C<check_bloat> subroutine. These values are ignored if either I<--exclude> or 
I<--include> is used.

Only the top 10 most bloated relations are shown. You can change this number by 
using the I<--perflimit> option to set your own limit.

The schema named 'information_schema' is excluded from this test, as the only tables 
it contains are small and do not change.

Please note that the values computed by this action are not precise, and 
should be used as a guideline only. Great effort was made to estimate the 
correct size of a table, but in the end it is only an estimate. The correct 
index size is even more of a guess than the correct table size, but both 
should give a rough idea of how bloated things are.

Example 1: Warn if any table on port 5432 is over 100 MB bloated, and critical if over 200 MB

  check_postgres_bloat --port=5432 --warning='100 M' --critical='200 M'

Example 2: Give a critical if table 'orders' on host 'sami' has more than 10 megs of bloat

  check_postgres_bloat --host=sami --include=orders --critical='10 MB'

Example 3: Give a critical if table 'q4' on database 'sales' is over 50% bloated

  check_postgres_bloat --db=sales --include=q4 --critical='50%'

Example 4: Give a critical any table is over 20% bloated I<and> has over 150
MB of bloat:

  check_postgres_bloat --port=5432 --critical='20% and 150 M'

Example 5: Give a critical any table is over 40% bloated I<or> has over 500 MB
of bloat:

  check_postgres_bloat --port=5432 --warning='500 M or 40%'

For MRTG output, the first line gives the highest number of wasted bytes for the tables, and the 
second line gives the highest number of wasted bytes for the indexes. The fourth line gives the database 
name, table name, and index name information. If you want to output the bloat ratio instead (how many 
times larger the relation is compared to how large it should be), just pass in C<--mrtg=ratio>.

=head2 B<checkpoint>

(C<symlink: check_postgres_checkpoint>) Determines how long since the last checkpoint has 
been run. This must run on the same server as the database that is being checked (e.g. the -h 
flag will not work). This check is meant to run on a "warm standby" server that is actively 
processing shipped WAL files, and is meant to check that your warm standby is truly 'warm'. 
The data directory must be set, either by the environment variable C<PGDATA>, or passing 
the C<--datadir> argument. It returns the number of seconds since the last checkpoint 
was run, as determined by parsing the call to C<pg_controldata>. Because of this, the 
pg_controldata executable must be available in the current path. Alternatively,
you can specify C<PGBINDIR> as the directory that it lives in.
It is also possible to use the special options I<--assume-prod> or
I<--assume-standby-mode>, if the mode found is not the one expected, a CRITICAL is emitted.

At least one warning or critical argument must be set.

This action requires the Date::Parse module.

For MRTG or simple output, returns the number of seconds.

=head2 B<cluster_id>

(C<symlink: check_postgres_cluster-id>) Checks that the Database System Identifier
provided by pg_controldata is the same as last time you checked. This must run on the same
server as the database that is being checked (e.g. the -h flag will not work).
Either the I<--warning> or the I<--critical> option should be given, but not both. The value
of each one is the cluster identifier, an integer value. You can run with the special C<--critical=0> option
to find out an existing cluster identifier.

Example 1: Find the initial identifier

  check_postgres_cluster_id --critical=0 --datadir=/var//lib/postgresql/9.0/main

Example 2: Make sure the cluster is the same and warn if not, using the result from above.

  check_postgres_cluster_id  --critical=5633695740047915135

For MRTG output, returns a 1 or 0 indicating success of failure of the identifier to match. A
identifier must be provided as the C<--mrtg> argument. The fourth line always gives the
current identifier.

=head2 B<commitratio>

(C<symlink: check_postgres_commitratio>) Checks the commit ratio of all databases and complains when they are too low.
There is no need to run this command more than once per database cluster. 
Databases can be filtered with 
the I<--include> and I<--exclude> options. See the L</"BASIC FILTERING"> section 
for more details. 
They can also be filtered by the owner of the database with the 
I<--includeuser> and I<--excludeuser> options.
See the L</"USER NAME FILTERING"> section for more details.

The warning and critical options should be specified as percentages. There are not
defaults for this action: the warning and critical must be specified. The warning value
cannot be greater than the critical value. The output returns all databases sorted by
commitratio, smallest first.

Example: Warn if any database on host flagg is less than 90% in commitratio, and critical if less then 80%.

  check_postgres_database_commitratio --host=flagg --warning='90%' --critical='80%'

For MRTG output, returns the percentage of the database with the smallest commitratio on the first line, 
and the name of the database on the fourth line.

=head2 B<connection>

(C<symlink: check_postgres_connection>) Simply connects, issues a 'SELECT version()', and leaves.
Takes no I<--warning> or I<--critical> options.

For MRTG output, simply outputs a 1 (good connection) or a 0 (bad connection) on the first line.

=head2 B<custom_query>

(C<symlink: check_postgres_custom_query>) Runs a custom query of your choosing, and parses the results. 
The query itself is passed in through the C<query> argument, and should be kept as simple as possible. 
If at all possible, wrap it in a view or a function to keep things easier to manage. The query should 
return one or two columns. It is required that one of the columns be named "result" and is the item 
that will be checked against your warning and critical values. The second column is for the performance 
data and any name can be used: this will be the 'value' inside the performance data section.

At least one warning or critical argument must be specified. What these are set to depends on the type of 
query you are running. There are four types of custom_queries that can be run, specified by the C<valtype> 
argument. If none is specified, this action defaults to 'integer'. The four types are:

B<integer>:
Does a simple integer comparison. The first column should be a simple integer, and the warning and 
critical values should be the same.

B<string>:
The warning and critical are strings, and are triggered only if the value in the first column matches 
it exactly. This is case-sensitive.

B<time>:
The warning and the critical are times, and can have units of seconds, minutes, hours, or days.
Each may be written singular or abbreviated to just the first letter. If no units are given, 
seconds are assumed. The first column should be an integer representing the number of seconds
to check.

B<size>:
The warning and the critical are sizes, and can have units of bytes, kilobytes, megabytes, gigabytes, 
terabytes, or exabytes. Each may be abbreviated to the first letter. If no units are given, 
bytes are assumed. The first column should be an integer representing the number of bytes to check.

Normally, an alert is triggered if the values returned are B<greater than> or equal to the critical or warning 
value. However, an option of I<--reverse> will trigger the alert if the returned value is 
B<lower than> or equal to the critical or warning value.

Example 1: Warn if any relation over 100 pages is named "rad", put the number of pages 
inside the performance data section.

  check_postgres_custom_query --valtype=string -w "rad" --query=
    "SELECT relname AS result, relpages AS pages FROM pg_class WHERE relpages > 100"

Example 2: Give a critical if the "foobar" function returns a number over 5MB:

  check_postgres_custom_query --critical='5MB'--valtype=size --query="SELECT foobar() AS result"

Example 2: Warn if the function "snazzo" returns less than 42:

  check_postgres_custom_query --critical=42 --query="SELECT snazzo() AS result" --reverse

If you come up with a useful custom_query, consider sending in a patch to this program 
to make it into a standard action that other people can use.

This action does not support MRTG or simple output yet.

=head2 B<database_size>

(C<symlink: check_postgres_database_size>) Checks the size of all databases and complains when they are too big. 
There is no need to run this command more than once per database cluster. 
Databases can be filtered with 
the I<--include> and I<--exclude> options. See the L</"BASIC FILTERING"> section 
for more details. 
They can also be filtered by the owner of the database with the 
I<--includeuser> and I<--excludeuser> options.
See the L</"USER NAME FILTERING"> section for more details.

The warning and critical options can be specified as bytes, kilobytes, megabytes, 
gigabytes, terabytes, or exabytes. Each may be abbreviated to the first letter as well. 
If no unit is given, the units are assumed to be bytes. There are not defaults for this 
action: the warning and critical must be specified. The warning value cannot be greater 
than the critical value. The output returns all databases sorted by size largest first, 
showing both raw bytes and a "pretty" version of the size.

Example 1: Warn if any database on host flagg is over 1 TB in size, and critical if over 1.1 TB.

  check_postgres_database_size --host=flagg --warning='1 TB' --critical='1.1 t'

Example 2: Give a critical if the database template1 on port 5432 is over 10 MB.

  check_postgres_database_size --port=5432 --include=template1 --warning='10MB' --critical='10MB'

Example 3: Give a warning if any database on host 'tardis' owned by the user 'tom' is over 5 GB

  check_postgres_database_size --host=tardis --includeuser=tom --warning='5 GB' --critical='10 GB'

For MRTG output, returns the size in bytes of the largest database on the first line, 
and the name of the database on the fourth line.

=head2 B<dbstats>

(C<symlink: check_postgres_dbstats>) Reports information from the pg_stat_database view, 
and outputs it in a Cacti-friendly manner. No other output is supported, as the output 
is informational and does not lend itself to alerts, such as used with Nagios. If no 
options are given, all databases are returned, one per line. You can include a specific 
database by use of the C<--include> option, or you can use the C<--dbname> option.

Eleven items are returned on each line, in the format name:value, separated by a single 
space. The items are:

=over 4

=item backends

The number of currently running backends for this database.

=item commits

The total number of commits for this database since it was created or reset.

=item rollbacks

The total number of rollbacks for this database since it was created or reset.

=item read

The total number of disk blocks read.

=item hit

The total number of buffer hits.

=item ret

The total number of rows returned.

=item fetch

The total number of rows fetched.

=item ins

The total number of rows inserted.

=item upd

The total number of rows updated.

=item del

The total number of rows deleted.

=item dbname

The name of the database.

=back

Note that ret, fetch, ins, upd, and del items will always be 0 if Postgres is version 8.2 or lower, as those stats were 
not available in those versions.

If the dbname argument is given, seven additional items are returned:

=over 4

=item idxscan

Total number of user index scans.

=item idxtupread

Total number of user index entries returned.

=item idxtupfetch

Total number of rows fetched by simple user index scans.

=item idxblksread

Total number of disk blocks read for all user indexes.

=item idxblkshit

Total number of buffer hits for all user indexes.

=item seqscan

Total number of sequential scans against all user tables.

=item seqtupread

Total number of tuples returned from all user tables.

=back

Example 1: Grab the stats for a database named "products" on host "willow":

  check_postgres_dbstats --dbhost willow --dbname products

The output returned will be like this (all on one line, not wrapped):

    backends:82 commits:58374408 rollbacks:1651 read:268435543 hit:2920381758 idxscan:310931294 idxtupread:2777040927
    idxtupfetch:1840241349 idxblksread:62860110 idxblkshit:1107812216 seqscan:5085305 seqtupread:5370500520
    ret:0 fetch:0 ins:0 upd:0 del:0 dbname:willow

=head2 B<disabled_triggers>

(C<symlink: check_postgres_disabled_triggers>) Checks on the number of disabled triggers inside the database.
The I<--warning> and I<--critical> options are the number of such triggers found, and both 
default to "1", as in normal usage having disabled triggers is a dangerous event. If the 
database being checked is 8.3 or higher, the check is for the number of triggers that are 
in a 'disabled' status (as opposed to being 'always' or 'replica'). The output will show 
the name of the table and the name of the trigger for each disabled trigger.

Example 1: Make sure that there are no disabled triggers

  check_postgres_disabled_triggers

For MRTG output, returns the number of disabled triggers on the first line.

=head2 B<disk_space>

(C<symlink: check_postgres_disk_space>) Checks on the available physical disk space used by Postgres. This action requires 
that you have the executable "/bin/df" available to report on disk sizes, and it 
also needs to be run as a superuser, so it can examine the B<data_directory> 
setting inside of Postgres. The I<--warning> and I<--critical> options are 
given in either sizes or percentages or both. If using sizes, the standard unit types 
are allowed: bytes, kilobytes, gigabytes, megabytes, gigabytes, terabytes, or 
exabytes. Each may be abbreviated to the first letter only; no units at all 
indicates 'bytes'. The default values are '90%' and '95%'.

This command checks the following things to determine all of the different 
physical disks being used by Postgres.

B<data_directory> - The disk that the main data directory is on.

B<log directory> - The disk that the log files are on.

B<WAL file directory> - The disk that the write-ahead logs are on (e.g. symlinked pg_xlog)

B<tablespaces> - Each tablespace that is on a separate disk.

The output shows the total size used and available on each disk, as well as 
the percentage, ordered by highest to lowest percentage used. Each item above 
maps to a file system: these can be included or excluded. See the 
L</"BASIC FILTERING"> section for more details.

Example 1: Make sure that no file system is over 90% for the database on port 5432.

  check_postgres_disk_space --port=5432 --warning='90%' --critical='90%'

Example 2: Check that all file systems starting with /dev/sda are smaller than 10 GB and 11 GB (warning and critical)

  check_postgres_disk_space --port=5432 --warning='10 GB' --critical='11 GB' --include="~^/dev/sda"

Example 4: Make sure that no file system is both over 50% I<and> has over 15 GB

  check_postgres_disk_space --critical='50% and 15 GB'

Example 5: Issue a warning if any file system is either over 70% full I<or> has
more than 1T

  check_postgres_disk_space --warning='1T or 75'

For MRTG output, returns the size in bytes of the file system on the first line, 
and the name of the file system on the fourth line.

=head2 B<fsm_pages>

(C<symlink: check_postgres_fsm_pages>) Checks how close a cluster is to the Postgres B<max_fsm_pages> setting.
This action will only work for databases of 8.2 or higher, and it requires the contrib
module B<pg_freespacemap> be installed. The I<--warning> and I<--critical> options should be expressed
as percentages. The number of used pages in the free-space-map is determined by looking in the
pg_freespacemap_relations view, and running a formula based on the formula used for
outputting free-space-map pageslots in the vacuum verbose command. The default values are B<85%> for the 
warning and B<95%> for the critical.

Example 1: Give a warning when our cluster has used up 76% of the free-space pageslots, with pg_freespacemap installed in database robert 

  check_postgres_fsm_pages --dbname=robert --warning="76%"

While you need to pass in the name of the database where pg_freespacemap is installed, you only need to run this check once per cluster. Also, checking this information does require obtaining special locks on the free-space-map, so it is recommend you do not run this check with short intervals.

For MRTG output, returns the percent of free-space-map on the first line, and the number of pages currently used on 
the second line.

=head2 B<fsm_relations>

(C<symlink: check_postgres_fsm_relations>) Checks how close a cluster is to the Postgres B<max_fsm_relations> setting. 
This action will only work for databases of 8.2 or higher, and it requires the contrib module B<pg_freespacemap> be 
installed. The I<--warning> and I<--critical> options should be expressed as percentages. The number of used relations 
in the free-space-map is determined by looking in the pg_freespacemap_relations view. The default values are B<85%> for 
the warning and B<95%> for the critical.

Example 1: Give a warning when our cluster has used up 80% of the free-space relations, with pg_freespacemap installed in database dylan

  check_postgres_fsm_relations --dbname=dylan --warning="75%"

While you need to pass in the name of the database where pg_freespacemap is installed, you only need to run this check 
once per cluster. Also,
checking this information does require obtaining special locks on the free-space-map, so it is recommend you do not
run this check with short intervals.

For MRTG output, returns the percent of free-space-map on the first line, the number of relations currently used on 
the second line.

=head2 B<hitratio>

(C<symlink: check_postgres_hitratio>) Checks the hit ratio of all databases and complains when they are too low.
There is no need to run this command more than once per database cluster. 
Databases can be filtered with 
the I<--include> and I<--exclude> options. See the L</"BASIC FILTERING"> section 
for more details. 
They can also be filtered by the owner of the database with the 
I<--includeuser> and I<--excludeuser> options.
See the L</"USER NAME FILTERING"> section for more details.

The warning and critical options should be specified as percentages. There are not
defaults for this action: the warning and critical must be specified. The warning value
cannot be greater than the critical value. The output returns all databases sorted by
hitratio, smallest first.

Example: Warn if any database on host flagg is less than 90% in hitratio, and critical if less then 80%.

  check_postgres_hitratio --host=flagg --warning='90%' --critical='80%'

For MRTG output, returns the percentage of the database with the smallest hitratio on the first line, 
and the name of the database on the fourth line.

=head2 B<hot_standby_delay>

(C<symlink: check_hot_standby_delay>) Checks the streaming replication lag by computing the delta 
between the current xlog position of a master server and the replay location of a slave connected
to it. The slave server must be in hot_standby (e.g. read only) mode, therefore the minimum version to use
this action is Postgres 9.0. The I<--warning> and I<--critical> options are the delta between the xlog
locations. Since these values are byte offsets in the WAL they should match the expected transaction volume
of your application to prevent false positives or negatives.

The first "--dbname", "--host", and "--port", etc. options are considered the
master; the second belongs to the slave.

Byte values should be based on the volume of transactions needed to have the streaming replication
disconnect from the master because of too much lag, determined by the Postgres configuration variable
B<wal_keep_segments>.  For units of time, valid units are 'seconds', 'minutes', 'hours', or 'days'.
Each may be written singular or abbreviated to just the first letter. When specifying both, in the
form 'I<bytes> and I<time>', both conditions must be true for the threshold to be met.

You must provide information on how to reach the databases by providing a comma separated list to the
--dbhost and --dbport parameters, such as "--dbport=5432,5543". If not given, the action fails.

Example 1: Warn a database with a local replica on port 5433 is behind on any xlog replay at all

  check_hot_standby_delay --dbport=5432,5433 --warning='1'

Example 2: Give a critical if the last transaction replica1 receives is more than 10 minutes ago

  check_hot_standby_delay --dbhost=master,replica1 --critical='10 min'

Example 3: Allow replica1 to be 1 WAL segment behind, if the master is momentarily seeing more activity than the streaming replication connection can handle, or 10 minutes behind, if the master is seeing very little activity and not processing any transactions, but not both, which would indicate a lasting problem with the replication connection.

  check_hot_standby_delay --dbhost=master,replica1 --warning='1048576 and 2 min' --critical='16777216 and 10 min'

=head2 B<index_size>

=head2 B<table_size>

=head2 B<relation_size>

(symlinks: C<check_postgres_index_size>, C<check_postgres_table_size>, and C<check_postgres_relation_size>)
The actions B<table_size> and B<index_size> are simply variations of the 
B<relation_size> action, which checks for a relation that has grown too big. 
Relations (in other words, tables and indexes) can be filtered with the 
I<--include> and I<--exclude> options. See the L</"BASIC FILTERING"> section 
for more details. Relations can also be filtered by the user that owns them, 
by using the I<--includeuser> and I<--excludeuser> options. 
See the L</"USER NAME FILTERING"> section for more details.

The values for the I<--warning> and I<--critical> options are file sizes, and 
may have units of bytes, kilobytes, megabytes, gigabytes, terabytes, or exabytes. 
Each can be abbreviated to the first letter. If no units are given, bytes are 
assumed. There are no default values: both the warning and the critical option 
must be given. The return text shows the size of the largest relation found.

If the I<--showperf> option is enabled, I<all> of the relations with their sizes 
will be given. To prevent this, it is recommended that you set the 
I<--perflimit> option, which will cause the query to do a 
C<ORDER BY size DESC LIMIT (perflimit)>.

Example 1: Give a critical if any table is larger than 600MB on host burrick.

  check_postgres_table_size --critical='600 MB' --warning='600 MB' --host=burrick

Example 2: Warn if the table products is over 4 GB in size, and give a critical at 4.5 GB.

  check_postgres_table_size --host=burrick --warning='4 GB' --critical='4.5 GB' --include=products

Example 3: Warn if any index not owned by postgres goes over 500 MB.

  check_postgres_index_size --port=5432 --excludeuser=postgres -w 500MB -c 600MB

For MRTG output, returns the size in bytes of the largest relation, and the name of the database 
and relation as the fourth line.

=head2 B<last_analyze>

=head2 B<last_vacuum>

=head2 B<last_autoanalyze>

=head2 B<last_autovacuum>

(symlinks: C<check_postgres_last_analyze>, C<check_postgres_last_vacuum>, 
C<check_postgres_last_autoanalyze>, and C<check_postgres_last_autovacuum>)
Checks how long it has been since vacuum (or analyze) was last run on each 
table in one or more databases. Use of these actions requires that the target 
database is version 8.3 or greater, or that the version is 8.2 and the 
configuration variable B<stats_row_level> has been enabled. Tables can be filtered with the 
I<--include> and I<--exclude> options. See the L</"BASIC FILTERING"> section 
for more details.
Tables can also be filtered by their owner by use of the 
I<--includeuser> and I<--excludeuser> options.
See the L</"USER NAME FILTERING"> section for more details.

The units for I<--warning> and I<--critical> are specified as times. 
Valid units are seconds, minutes, hours, and days; all can be abbreviated 
to the first letter. If no units are given, 'seconds' are assumed. The 
default values are '1 day' and '2 days'. Please note that there are cases 
in which this field does not get automatically populated. If certain tables 
are giving you problems, make sure that they have dead rows to vacuum, 
or just exclude them from the test.

The schema named 'information_schema' is excluded from this test, as the only tables 
it contains are small and do not change.

Note that the non-'auto' versions will also check on the auto versions as well. In other words, 
using last_vacuum will report on the last vacuum, whether it was a normal vacuum, or 
one run by the autovacuum daemon.

Example 1: Warn if any table has not been vacuumed in 3 days, and give a 
critical at a week, for host wormwood

  check_postgres_last_vacuum --host=wormwood --warning='3d' --critical='7d'

Example 2: Same as above, but skip tables belonging to the users 'eve' or 'mallory'

  check_postgres_last_vacuum --host=wormwood --warning='3d' --critical='7d' --excludeusers=eve,mallory

For MRTG output, returns (on the first line) the LEAST amount of time in seconds since a table was 
last vacuumed or analyzed. The fourth line returns the name of the database and name of the table.

=head2 B<listener>

(C<symlink: check_postgres_listener>) Confirm that someone is listening for one or more 
specific strings (using the LISTEN/NOTIFY system), by looking at the pg_listener table. 
Only one of warning or critical is needed. The format is a simple string representing the 
LISTEN target, or a tilde character followed by a string for a regular expression check.
Note that this check will not work on versions of Postgres 9.0 or higher.

Example 1: Give a warning if nobody is listening for the string bucardo_mcp_ping on ports 5555 and 5556

  check_postgres_listener --port=5555,5556 --warning=bucardo_mcp_ping

Example 2: Give a critical if there are no active LISTEN requests matching 'grimm' on database oskar

  check_postgres_listener --db oskar --critical=~grimm

For MRTG output, returns a 1 or a 0 on the first, indicating success or failure. The name of the notice must 
be provided via the I<--mrtg> option.

=head2 B<locks>

(C<symlink: check_postgres_locks>) Check the total number of locks on one or more databases. There is no 
need to run this more than once per database cluster. Databases can be filtered 
with the I<--include> and I<--exclude> options. See the L</"BASIC FILTERING"> section 
for more details.

The I<--warning> and I<--critical> options can be specified as simple numbers, 
which represent the total number of locks, or they can be broken down by type of lock. 
Valid lock names are C<'total'>, C<'waiting'>, or the name of a lock type used by Postgres. 
These names are case-insensitive and do not need the "lock" part on the end, 
so B<exclusive> will match 'ExclusiveLock'. The format is name=number, with different 
items separated by colons or semicolons (or any other symbol).

Example 1: Warn if the number of locks is 100 or more, and critical if 200 or more, on host garrett

  check_postgres_locks --host=garrett --warning=100 --critical=200

Example 2: On the host artemus, warn if 200 or more locks exist, and give a critical if over 250 total locks exist, or if over 20 exclusive locks exist, or if over 5 connections are waiting for a lock.

  check_postgres_locks --host=artemus --warning=200 --critical="total=250:waiting=5:exclusive=20"

For MRTG output, returns the number of locks on the first line, and the name of the database on the fourth line.

=head2 B<logfile>

(C<symlink: check_postgres_logfile>) Ensures that the logfile is in the expected location and is being logged to. 
This action issues a command that throws an error on each database it is 
checking, and ensures that the message shows up in the logs. It scans the 
various log_* settings inside of Postgres to figure out where the logs should be. 
If you are using syslog, it does a rough (but not foolproof) scan of 
F</etc/syslog.conf>. Alternatively, you can provide the name of the logfile 
with the I<--logfile> option. This is especially useful if the logs have a 
custom rotation scheme driven be an external program. The B<--logfile> option 
supports the following escape characters: C<%Y %m %d %H>, which represent 
the current year, month, date, and hour respectively. An error is always 
reported as critical unless the warning option has been passed in as a non-zero 
value. Other than that specific usage, the C<--warning> and C<--critical> 
options should I<not> be used.

Example 1: On port 5432, ensure the logfile is being written to the file /home/greg/pg8.2.log

  check_postgres_logfile --port=5432 --logfile=/home/greg/pg8.2.log

Example 2: Same as above, but raise a warning, not a critical

  check_postgres_logfile --port=5432 --logfile=/home/greg/pg8.2.log -w 1

For MRTG output, returns a 1 or 0 on the first line, indicating success or failure. In case of a 
failure, the fourth line will provide more detail on the failure encountered.

=head2 B<new_version_bc>

(C<symlink: check_postgres_new_version_bc>) Checks if a newer version of the Bucardo 
program is available. The current version is obtained by running C<bucardo_ctl --version>.
If a major upgrade is available, a warning is returned. If a revision upgrade is 
available, a critical is returned. (Bucardo is a master to slave, and master to master 
replication system for Postgres: see http://bucardo.org for more information).
See also the information on the C<--get_method> option.

=head2 B<new_version_box>

(C<symlink: check_postgres_new_version_box>) Checks if a newer version of the boxinfo 
program is available. The current version is obtained by running C<boxinfo.pl --version>.
If a major upgrade is available, a warning is returned. If a revision upgrade is 
available, a critical is returned. (boxinfo is a program for grabbing important 
information from a server and putting it into a HTML format: see 
http://bucardo.org/wiki/boxinfo for more information). See also the information on 
the C<--get_method> option.

=head2 B<new_version_cp>

(C<symlink: check_postgres_new_version_cp>) Checks if a newer version of this program 
(check_postgres.pl) is available, by grabbing the version from a small text file 
on the main page of the home page for the project. Returns a warning if the returned 
version does not match the one you are running. Recommended interval to check is 
once a day. See also the information on the C<--get_method> option.

=head2 B<new_version_pg>

(C<symlink: check_postgres_new_version_pg>) Checks if a newer revision of Postgres 
exists for each database connected to. Note that this only checks for revision, e.g. 
going from 8.3.6 to 8.3.7. Revisions are always 100% binary compatible and involve no 
dump and restore to upgrade. Revisions are made to address bugs, so upgrading as soon 
as possible is always recommended. Returns a warning if you do not have the latest revision.
It is recommended this check is run at least once a day. See also the information on 
the C<--get_method> option.


=head2 B<new_version_tnm>

(C<symlink: check_postgres_new_version_tnm>) Checks if a newer version of the 
tail_n_mail program is available. The current version is obtained by running 
C<tail_n_mail --version>. If a major upgrade is available, a warning is returned. If a 
revision upgrade is available, a critical is returned. (tail_n_mail is a log monitoring 
tool that can send mail when interesting events appear in your Postgres logs.
See: http://bucardo.org/wiki/Tail_n_mail for more information).
See also the information on the C<--get_method> option.

=head2 B<pgb_pool_cl_active>

=head2 B<pgb_pool_cl_waiting>

=head2 B<pgb_pool_sv_active>

=head2 B<pgb_pool_sv_idle>

=head2 B<pgb_pool_sv_used>

=head2 B<pgb_pool_sv_tested>

=head2 B<pgb_pool_sv_login>

=head2 B<pgb_pool_maxwait>

(symlinks: C<check_postgres_pgb_pool_cl_active>, C<check_postgres_pgb_pool_cl_waiting>,
C<check_postgres_pgb_pool_sv_active>, C<check_postgres_pgb_pool_sv_idle>,
C<check_postgres_pgb_pool_sv_used>, C<check_postgres_pgb_pool_sv_tested>,
C<check_postgres_pgb_pool_sv_login>, and C<check_postgres_pgb_pool_maxwait>)

Examines pgbouncer's pool statistics. Each pool has a set of "client"
connections, referring to connections from external clients, and "server"
connections, referring to connections to PostgreSQL itself. The related
check_postgres actions are prefixed by "cl_" and "sv_", respectively. Active
client connections are those connections currently linked with an active server
connection. Client connections may also be "waiting", meaning they have not yet
been allocated a server connection. Server connections are "active" (linked to
a client), "idle" (standing by for a client connection to link with), "used"
(just unlinked from a client, and not yet returned to the idle pool), "tested"
(currently being tested) and "login" (in the process of logging in). The
maxwait value shows how long in seconds the oldest waiting client connection
has been waiting.

=head2 B<pgbouncer_backends>

(C<symlink: check_postgres_pgbouncer_backends>) Checks the current number of
connections for one or more databases through pgbouncer, and optionally
compares it to the maximum allowed, which is determined by the pgbouncer
configuration variable B<max_client_conn>. The I<--warning> and I<--critical>
options can take one of three forms. First, a simple number can be given,
which represents the number of connections at which the alert will be given.
This choice does not use the B<max_connections> setting. Second, the
percentage of available connections can be given. Third, a negative number can
be given which represents the number of connections left until
B<max_connections> is reached. The default values for I<--warning> and
I<--critical> are '90%' and '95%'.  You can also filter the databases by use
of the I<--include> and I<--exclude> options.  See the L</"BASIC FILTERING">
section for more details.

To view only non-idle processes, you can use the I<--noidle> argument. Note
that the user you are connecting as must be a superuser for this to work
properly.

Example 1: Give a warning when the number of connections on host quirm reaches
120, and a critical if it reaches 150.

  check_postgres_pgbouncer_backends --host=quirm --warning=120 --critical=150 -p 6432 -u pgbouncer

Example 2: Give a critical when we reach 75% of our max_connections setting on
hosts lancre or lancre2.

  check_postgres_pgbouncer_backends --warning='75%' --critical='75%' --host=lancre,lancre2 -p 6432 -u pgbouncer

Example 3: Give a warning when there are only 10 more connection slots left on
host plasmid, and a critical when we have only 5 left.

  check_postgres_pgbouncer_backends --warning=-10 --critical=-5 --host=plasmid -p 6432 -u pgbouncer

For MRTG output, the number of connections is reported on the first line, and
the fourth line gives the name of the database, plus the current
max_client_conn. If more than one database has been queried, the one with the
highest number of connections is output.

=head2 B<pgbouncer_checksum>

(C<symlink: check_postgres_pgbouncer_checksum>) Checks that all the
pgBouncer settings are the same as last time you checked. 
This is done by generating a checksum of a sorted list of setting names and 
their values. Note that you shouldn't specify the database name, it will
automatically default to pgbouncer.  Either the I<--warning> or the I<--critical> option 
should be given, but not both. The value of each one is the checksum, a 
32-character hexadecimal value. You can run with the special C<--critical=0> option 
to find out an existing checksum.

This action requires the Digest::MD5 module.

Example 1: Find the initial checksum for pgbouncer configuration on port 6432 using the default user (usually postgres)

  check_postgres_pgbouncer_checksum --port=6432 --critical=0

Example 2: Make sure no settings have changed and warn if so, using the checksum from above.

  check_postgres_pgbouncer_checksum --port=6432 --warning=cd2f3b5e129dc2b4f5c0f6d8d2e64231

For MRTG output, returns a 1 or 0 indicating success of failure of the checksum to match. A 
checksum must be provided as the C<--mrtg> argument. The fourth line always gives the 
current checksum.

=head2 B<pgagent_jobs>

(C<symlink: check_postgres_pgagent_jobs>) Checks that all the pgAgent jobs
that have executed in the preceding interval of time have succeeded. This is
done by checking for any steps that have a non-zero result.

Either C<--warning> or C<--critical>, or both, may be specified as times, and
jobs will be checked for failures withing the specified periods of time before
the current time. Valid units are seconds, minutes, hours, and days; all can
be abbreviated to the first letter. If no units are given, 'seconds' are
assumed.

Example 1: Give a critical when any jobs executed in the last day have failed.

  check_postgres_pgagent_jobs --critical=1d

Example 2: Give a warning when any jobs executed in the last week have failed.

  check_postgres_pgagent_jobs --warning=7d

Example 3: Give a critical for jobs that have failed in the last 2 hours and a
warning for jobs that have failed in the last 4 hours:

  check_postgres_pgagent_jobs --critical=2h --warning=4h

=head2 B<prepared_txns>

(C<symlink: check_postgres_prepared_txns>) Check on the age of any existing prepared transactions. 
Note that most people will NOT use prepared transactions, as they are part of two-part commit 
and complicated to maintain. They should also not be confused with prepared STATEMENTS, which is 
what most people think of when they hear prepare. The default value for a warning is 1 second, to 
detect any use of prepared transactions, which is probably a mistake on most systems. Warning and 
critical are the number of seconds a prepared transaction has been open before an alert is given.

Example 1: Give a warning on detecting any prepared transactions:

  check_postgres_prepared_txns -w 0

Example 2: Give a critical if any prepared transaction has been open longer than 10 seconds, but allow 
up to 360 seconds for the database 'shrike':

  check_postgres_prepared_txns --critical=10 --exclude=shrike
  check_postgres_prepared_txns --critical=360 --include=shrike

For MRTG output, returns the number of seconds the oldest transaction has been open as the first line, 
and which database is came from as the final line.

=head2 B<query_runtime>

(C<symlink: check_postgres_query_runtime>) Checks how long a specific query takes to run, by executing a "EXPLAIN ANALYZE" 
against it. The I<--warning> and I<--critical> options are the maximum amount of 
time the query should take. Valid units are seconds, minutes, and hours; any can be 
abbreviated to the first letter. If no units are given, 'seconds' are assumed. 
Both the warning and the critical option must be given. The name of the view or 
function to be run must be passed in to the I<--queryname> option. It must consist 
of a single word (or schema.word), with optional parens at the end.

Example 1: Give a critical if the function named "speedtest" fails to run in 10 seconds or less.

  check_postgres_query_runtime --queryname='speedtest()' --critical=10 --warning=10

For MRTG output, reports the time in seconds for the query to complete on the first line. The fourth 
line lists the database.

=head2 B<query_time>

(C<symlink: check_postgres_query_time>) Checks the length of running queries on one or more databases. 
There is no need to run this more than once on the same database cluster. Note that 
this already excludes queries that are "idle in transaction". Databases can be filtered 
by using the I<--include> and I<--exclude> options. See the L</"BASIC FILTERING">
section for more details. You can also filter on the user running the 
query with the I<--includeuser> and I<--excludeuser> options.
See the L</"USER NAME FILTERING"> section for more details.

The values for the I<--warning> and I<--critical> options are amounts of 
time, and default to '2 minutes' and '5 minutes' respectively. Valid units 
are 'seconds', 'minutes', 'hours', or 'days'. Each may be written singular or 
abbreviated to just the first letter. If no units are given, the unit is 
assumed to be seconds.

This action requires Postgres 8.1 or better.

Example 1: Give a warning if any query has been running longer than 3 minutes, and a critical if longer than 5 minutes.

  check_postgres_query_time --port=5432 --warning='3 minutes' --critical='5 minutes'

Example 2: Using default values (2 and 5 minutes), check all databases except those starting with 'template'.

  check_postgres_query_time --port=5432 --exclude=~^template

Example 3: Warn if user 'don' has a query running over 20 seconds

  check_postgres_query_time --port=5432 --includeuser=don --warning=20s

For MRTG output, returns the length in seconds of the longest running query on the first line. The fourth 
line gives the name of the database.

=head2 B<replicate_row>

(C<symlink: check_postgres_replicate_row>) Checks that master-slave replication is working to one or more slaves.

The first "--dbname", "--host", and "--port", etc. options are considered the
master; subsequent uses are the slaves.
The values or the I<--warning> and I<--critical> options are units of time, and 
at least one must be provided (no defaults). Valid units are 'seconds', 'minutes', 'hours', 
or 'days'. Each may be written singular or abbreviated to just the first letter. 
If no units are given, the units are assumed to be seconds.

This check updates a single row on the master, and then measures how long it 
takes to be applied to the slaves. To do this, you need to pick a table that 
is being replicated, then find a row that can be changed, and is not going 
to be changed by any other process. A specific column of this row will be changed 
from one value to another. All of this is fed to the C<repinfo> option, and should 
contain the following options, separated by commas: table name, primary key, key id, 
column, first value, second value.

Example 1: Slony is replicating a table named 'orders' from host 'alpha' to 
host 'beta', in the database 'sales'. The primary key of the table is named 
id, and we are going to test the row with an id of 3 (which is historical and 
never changed). There is a column named 'salesrep' that we are going to toggle 
from a value of 'slon' to 'nols' to check on the replication. We want to throw 
a warning if the replication does not happen within 10 seconds.

  check_postgres_replicate_row --host=alpha --dbname=sales --host=beta
  --dbname=sales --warning=10 --repinfo=orders,id,3,salesrep,slon,nols

Example 2: Bucardo is replicating a table named 'receipt' from host 'green' 
to hosts 'red', 'blue', and 'yellow'. The database for both sides is 'public'. 
The slave databases are running on port 5455. The primary key is named 'receipt_id', 
the row we want to use has a value of 9, and the column we want to change for the 
test is called 'zone'. We'll toggle between 'north' and 'south' for the value of 
this column, and throw a critical if the change is not on all three slaves within 5 seconds.

 check_postgres_replicate_row --host=green --port=5455 --host=red,blue,yellow
  --critical=5 --repinfo=receipt,receipt_id,9,zone,north,south

For MRTG output, returns on the first line the time in seconds the replication takes to finish. 
The maximum time is set to 4 minutes 30 seconds: if no replication has taken place in that long 
a time, an error is thrown.

=head2 B<same_schema>

(C<symlink: check_postgres_same_schema>) Verifies that two or more databases are identical as far as their 
schema (but not the data within). This is particularly handy for making sure your slaves have not 
been modified or corrupted in any way when using master to slave replication. Unlike most other 
actions, this has no warning or critical criteria - the databases are either in sync, or are not. 
If they are different, a detailed list of the differences is presented.

You may want to exclude or filter out certain differences. The way to do this is to add strings 
to the C<--filter> option. To exclude a type of object, use "noname", where 'name' is the type of 
object, for example, "noschema". To exclude objects of a certain type by a regular expression against 
their name, use "noname=regex". See the examples below for a better understanding.

The types of objects that can be filtered include:

=over 4

=item user

=item schema

=item table

=item view

=item index

=item sequence

=item constraint

=item trigger

=item function

=back

The filter option "noposition"  prevents verification of the position of 
columns within a table.

The filter option "nofuncbody" prevents comparison of the bodies of all 
functions.

The filter option "noperm" prevents comparison of object permissions.

To provide the second database, just append the differences to the first one 
by a call to the appropriate connection argument. For example, to compare 
databases on hosts alpha and bravo, use "--dbhost=alpha,bravo". Also see the 
examples below.

If only a single host is given, it is assumed we are doing a "time-based" report. 
The first time this is run a snapshot of all the items in the database is 
saved to a local file. When you run it again, that snapshot is read in and 
becomes "database #2" and is compared to the current database.

To replace the old stored file with the new version, use the --replace argument.

To enable snapshots at various points in time, you can use the "--suffix" 
argument to make the filenames unique to each run. See the examples below.

Example 1: Verify that two databases on hosts star and line are the same:

  check_postgres_same_schema --dbhost=star,line

Example 2: Same as before, but exclude any triggers with "slony" in their name

  check_postgres_same_schema --dbhost=star,line --filter="notrigger=slony"

Example 3: Same as before, but also exclude all indexes

  check_postgres_same_schema --dbhost=star,line --filter="notrigger=slony noindexes"

Example 4: Check differences for the database "battlestar" on different ports

  check_postgres_same_schema --dbname=battlestar --dbport=5432,5544

Example 5: Create a daily and weekly snapshot file

  check_postgres_same_schema --dbname=cylon --suffix=daily
  check_postgres_same_schema --dbname=cylon --suffix=weekly

Example 6: Run a historical comparison, then replace the file

  check_postgres_same_schema --dbname=cylon --suffix=daily --replace

=head2 B<sequence>

(C<symlink: check_postgres_sequence>) Checks how much room is left on all sequences in the database.
This is measured as the percent of total possible values that have been used for each sequence. 
The I<--warning> and I<--critical> options should be expressed as percentages. The default values 
are B<85%> for the warning and B<95%> for the critical. You may use --include and --exclude to 
control which sequences are to be checked. Note that this check does account for unusual B<minvalue> 
and B<increment by> values, but does not care if the sequence is set to cycle or not.

The output for Nagios gives the name of the sequence, the percentage used, and the number of 'calls' 
left, indicating how many more times nextval can be called on that sequence before running into 
the maximum value.

The output for MRTG returns the highest percentage across all sequences on the first line, and 
the name of each sequence with that percentage on the fourth line, separated by a "|" (pipe) 
if there are more than one sequence at that percentage.

Example 1: Give a warning if any sequences are approaching 95% full.

  check_postgres_sequence --dbport=5432 --warning=95%

Example 2: Check that the sequence named "orders_id_seq" is not more than half full.

  check_postgres_sequence --dbport=5432 --critical=50% --include=orders_id_seq

=head2 B<settings_checksum>

(C<symlink: check_postgres_settings_checksum>) Checks that all the Postgres settings are the same as last time you checked. 
This is done by generating a checksum of a sorted list of setting names and 
their values. Note that different users in the same database may have different 
checksums, due to ALTER USER usage, and due to the fact that superusers see more 
settings than ordinary users. Either the I<--warning> or the I<--critical> option 
should be given, but not both. The value of each one is the checksum, a 
32-character hexadecimal value. You can run with the special C<--critical=0> option 
to find out an existing checksum.

This action requires the Digest::MD5 module.

Example 1: Find the initial checksum for the database on port 5555 using the default user (usually postgres)

  check_postgres_settings_checksum --port=5555 --critical=0

Example 2: Make sure no settings have changed and warn if so, using the checksum from above.

  check_postgres_settings_checksum --port=5555 --warning=cd2f3b5e129dc2b4f5c0f6d8d2e64231

For MRTG output, returns a 1 or 0 indicating success of failure of the checksum to match. A 
checksum must be provided as the C<--mrtg> argument. The fourth line always gives the 
current checksum.

=head2 B<slony_status>

(C<symlink: check_postgres_slony_status>) Checks in the status of a Slony cluster by looking 
at the results of Slony's sl_status view. This is returned as the number of seconds of "lag time". 
The I<--warning> and I<--critical> options should be expressed as times. The default values 
are B<60 seconds> for the warning and B<300 seconds> for the critical.

The optional argument I<--schema> indicated the schema that Slony is installed under. If it is 
not given, the schema will be determined automatically each time this check is run.

Example 1: Give a warning if any Slony is lagged by more than 20 seconds

  check_postgres_slony_status --warning 20

Example 2: Give a critical if Slony, installed under the schema "_slony", is over 10 minutes lagged

  check_postgres_slony_status --schema=_slony --critical=600

=head2 B<timesync>

(C<symlink: check_postgres_timesync>) Compares the local system time with the time reported by one or more databases. 
The I<--warning> and I<--critical> options represent the number of seconds between 
the two systems before an alert is given. If neither is specified, the default values 
are used, which are '2' and '5'. The warning value cannot be greater than the critical
value. Due to the non-exact nature of this test, values of '0' or '1' are not recommended.

The string returned shows the time difference as well as the time on each side written out.

Example 1: Check that databases on hosts ankh, morpork, and klatch are no more than 3 seconds off from the local time:

  check_postgres_timesync --host=ankh,morpork,klatch --critical=3

For MRTG output, returns one the first line the number of seconds difference between the local 
time and the database time. The fourth line returns the name of the database.

=head2 B<txn_idle>

(C<symlink: check_postgres_txn_idle>) Checks the number and duration of "idle
in transaction" queries on one or more databases. There is no need to run this
more than once on the same database cluster. Databases can be filtered by
using the I<--include> and I<--exclude> options. See the L</"BASIC FILTERING">
section below for more details.

The I<--warning> and I<--critical> options are given as units of time, signed
integers, or integers for units of time, and both must be provided (there are
no defaults). Valid units are 'seconds', 'minutes', 'hours', or 'days'. Each
may be written singular or abbreviated to just the first letter. If no units
are given and the numbers are unsigned, the units are assumed to be seconds.

This action requires Postgres 8.3 or better.

Example 1: Give a warning if any connection has been idle in transaction for more than 15 seconds:

  check_postgres_txn_idle --port=5432 --warning='15 seconds'

Example 2: Give a warning if there are 50 or more transactions

  check_postgres_txn_idle --port=5432 --warning='+50'

Example 3: Give a critical if 5 or more connections have been idle in
transaction for more than 10 seconds:

  check_postgres_txn_idle --port=5432 --critical='5 for 10 seconds'

For MRTG output, returns the time in seconds the longest idle transaction has been running. The fourth 
line returns the name of the database and other information about the longest transaction.

=head2 B<txn_time>

(C<symlink: check_postgres_txn_time>) Checks the length of open transactions on one or more databases. 
There is no need to run this command more than once per database cluster. 
Databases can be filtered by use of the 
I<--include> and I<--exclude> options. See the L</"BASIC FILTERING"> section 
for more details. The owner of the transaction can also be filtered, by use of 
the I<--includeuser> and I<--excludeuser> options.
See the L</"USER NAME FILTERING"> section for more details.

The values or the I<--warning> and I<--critical> options are units of time, and 
must be provided (no default). Valid units are 'seconds', 'minutes', 'hours', 
or 'days'. Each may be written singular or abbreviated to just the first letter. 
If no units are given, the units are assumed to be seconds.

This action requires Postgres 8.3 or better.

Example 1: Give a critical if any transaction has been open for more than 10 minutes:

  check_postgres_txn_time --port=5432 --critical='10 minutes'

Example 1: Warn if user 'warehouse' has a transaction open over 30 seconds

  check_postgres_txn_time --port-5432 --warning=30s --includeuser=warehouse

For MRTG output, returns the maximum time in seconds a transaction has been open on the 
first line. The fourth line gives the name of the database.

=head2 B<txn_wraparound>

(C<symlink: check_postgres_txn_wraparound>) Checks how close to transaction wraparound one or more databases are getting. 
The I<--warning> and I<--critical> options indicate the number of transactions done, and must be a positive integer. 
If either option is not given, the default values of 1.3 and 1.4 billion are used. There is no need to run this command 
more than once per database cluster. For a more detailed discussion of what this number represents and what to do about 
it, please visit the page 
L<http://www.postgresql.org/docs/current/static/routine-vacuuming.html#VACUUM-FOR-WRAPAROUND>

The warning and critical values can have underscores in the number for legibility, as Perl does.

Example 1: Check the default values for the localhost database

  check_postgres_txn_wraparound --host=localhost

Example 2: Check port 6000 and give a critical when 1.7 billion transactions are hit:

  check_postgres_txn_wraparound --port=6000 --critical=1_700_000_000

For MRTG output, returns the highest number of transactions for all databases on line one,
while line 4 indicates which database it is.

=head2 B<version>

(C<symlink: check_postgres_version>) Checks that the required version of Postgres is running. The 
I<--warning> and I<--critical> options (only one is required) must be of 
the format B<X.Y> or B<X.Y.Z> where B<X> is the major version number, 
B<Y> is the minor version number, and B<Z> is the revision.

Example 1: Give a warning if the database on port 5678 is not version 8.4.10:

  check_postgres_version --port=5678 -w=8.4.10

Example 2: Give a warning if any databases on hosts valley,grain, or sunshine is not 8.3:

  check_postgres_version -H valley,grain,sunshine --critical=8.3

For MRTG output, reports a 1 or a 0 indicating success or failure on the first line. The 
fourth line indicates the current version. The version must be provided via the C<--mrtg> option.

=head2 B<wal_files>

(C<symlink: check_postgres_wal_files>) Checks how many WAL files exist in the F<pg_xlog> directory, which is found 
off of your B<data_directory>, sometimes as a symlink to another physical disk for 
performance reasons. This action must be run as a superuser, in order to access the 
contents of the F<pg_xlog> directory. The minimum version to use this action is 
Postgres 8.1. The I<--warning> and I<--critical> options are simply the number of 
files in the F<pg_xlog> directory. What number to set this to will vary, but a general 
guideline is to put a number slightly higher than what is normally there, to catch 
problems early.

Normally, WAL files are closed and then re-used, but a long-running open 
transaction, or a faulty B<archive_command> script, may cause Postgres to 
create too many files. Ultimately, this will cause the disk they are on to run 
out of space, at which point Postgres will shut down.

Example 1: Check that the number of WAL files is 20 or less on host "pluto"

  check_postgres_wal_files --host=pluto --critical=20

For MRTG output, reports the number of WAL files on line 1.

=head2 B<rebuild_symlinks>

=head2 B<rebuild_symlinks_force>

This action requires no other arguments, and does not connect to any databases, 
but simply creates symlinks in the current directory for each action, in the form 
B<check_postgres_E<lt>action_nameE<gt>>.
If the file already exists, it will not be overwritten. If the action is rebuild_symlinks_force, 
then symlinks will be overwritten. The option --symlinks is a shorter way of saying 
--action=rebuild_symlinks

=head1 BASIC FILTERING

The options I<--include> and I<--exclude> can be combined to limit which 
things are checked, depending on the action. The name of the database can 
be filtered when using the following actions: 
backends, database_size, locks, query_time, txn_idle, and txn_time.
The name of a relation can be filtered when using the following actions: 
bloat, index_size, table_size, relation_size, last_vacuum, last_autovacuum, 
last_analyze, and last_autoanalyze.
The name of a setting can be filtered when using the settings_checksum action.
The name of a file system can be filtered when using the disk_space action.

If only an include option is given, then ONLY those entries that match will be 
checked. However, if given both exclude and include, the exclusion is done first, 
and the inclusion after, to reinstate things that may have been excluded. Both 
I<--include> and I<--exclude> can be given multiple times, 
and/or as comma-separated lists. A leading tilde will match the following word 
as a regular expression.

To match a schema, end the search term with a single period. Leading tildes can 
be used for schemas as well.

Be careful when using filtering: an inclusion rule on the backends, for example, 
may report no problems not only because the matching database had no backends, 
but because you misspelled the name of the database!

Examples:

Only checks items named pg_class:

 --include=pg_class

Only checks items containing the letters 'pg_':

 --include=~pg_

Only check items beginning with 'pg_':

 --include=~^pg_

Exclude the item named 'test':

 --exclude=test

Exclude all items containing the letters 'test:

 --exclude=~test

Exclude all items in the schema 'pg_catalog':

 --exclude='pg_catalog.'

Exclude all items containing the letters 'ace', but allow the item 'faceoff':

 --exclude=~ace --include=faceoff

Exclude all items which start with the letters 'pg_', which contain the letters 'slon', 
or which are named 'sql_settings' or 'green'. Specifically check items with the letters 'prod' in their names, and always check the item named 'pg_relname':

 --exclude=~^pg_,~slon,sql_settings --exclude=green --include=~prod,pg_relname

=head1 USER NAME FILTERING

The options I<--includeuser> and I<--excludeuser> can be used on some actions 
to only examine database objects owned by (or not owned by) one or more users. 
An I<--includeuser> option always trumps an I<--excludeuser> option. You can 
give each option more than once for multiple users, or you can give a 
comma-separated list. The actions that currently use these options are:

=over 4

=item database_size

=item last_analyze

=item last_autoanalyze

=item last_vacuum

=item last_autovacuum

=item query_time

=item relation_size

=item txn_time

=back

Examples:

Only check items owned by the user named greg:

 --includeuser=greg

Only check items owned by either watson or crick:

 --includeuser=watson,crick

Only check items owned by crick,franklin, watson, or wilkins:

 --includeuser=watson --includeuser=franklin --includeuser=crick,wilkins

Check all items except for those belonging to the user scott:

 --excludeuser=scott

=head1 TEST MODE

To help in setting things up, this program can be run in a "test mode" by 
specifying the I<--test> option. This will perform some basic tests to 
make sure that the databases can be contacted, and that certain per-action 
prerequisites are met, such as whether the user is a superuser, if the version 
of Postgres is new enough, and if stats_row_level is enabled.

=head1 FILES

In addition to command-line configurations, you can put any options inside of a file. The file 
F<.check_postgresrc> in the current directory will be used if found. If not found, then the file 
F<~/.check_postgresrc> will be used. Finally, the file /etc/check_postgresrc will be used if available. 
The format of the file is option = value, one per line. Any line starting with a '#' will be skipped. 
Any values loaded from a check_postgresrc file will be overwritten by command-line options. All 
check_postgresrc files can be ignored by supplying a C<--no-checkpostgresrc> argument.

=head1 ENVIRONMENT VARIABLES

The environment variable I<$ENV{HOME}> is used to look for a F<.check_postgresrc> file.
The environment variable I<$ENV{PGBINDIR}> is used to look for PostgreSQL binaries.

=head1 TIPS AND TRICKS

Since this program uses the B<psql> program, make sure it is accessible to the 
user running the script. If run as a cronjob, this often means modifying the 
B<PATH> environment variable.

If you are using Nagios in embedded Perl mode, use the C<--action> argument 
instead of symlinks, so that the plugin only gets compiled one time.

=head1 DEPENDENCIES

Access to a working version of psql, and the following very standard Perl modules:

=over 4

=item B<Cwd>

=item B<Getopt::Long>

=item B<File::Basename>

=item B<File::Temp>

=item B<Time::HiRes> (if C<$opt{showtime}> is set to true, which is the default)

=back

The L</settings_checksum> action requires the B<Digest::MD5> module.

The L</checkpoint> action requires the B<Date::Parse> module.

Some actions require access to external programs. If psql is not explicitly 
specified, the command B<C<which>> is used to find it. The program B<C</bin/df>> 
is needed by the L</disk_space> action.

=head1 DEVELOPMENT

Development happens using the git system. You can clone the latest version by doing:

 git clone git://bucardo.org/check_postgres.git

=head1 MAILING LIST

Three mailing lists are available. For discussions about the program, bug reports, 
feature requests, and commit notices, send email to check_postgres@bucardo.org

https://mail.endcrypt.com/mailman/listinfo/check_postgres

A low-volume list for announcement of new versions and important notices is the 
'check_postgres-announce' list:

https://mail.endcrypt.com/mailman/listinfo/check_postgres-announce

Source code changes (via git-commit) are sent to the 
'check_postgres-commit' list:

https://mail.endcrypt.com/mailman/listinfo/check_postgres-commit

=head1 HISTORY

Items not specifically attributed are by GSM (Greg Sabino Mullane).

=over 4

=item B<Version 2.22.0> June 30, 2015

  Add xact timestamp support to hot_standby_delay.
  Allow the hot_standby_delay check to accept xlog byte position or
  timestamp lag intervals as thresholds, or even both at the same time.
    (Josh Williams)

  Query all sequences per DB in parallel for action=sequence.
    (Christoph Berg)

  Fix bloat check to use correct SQL depending on the server version.
    (Adrian Vondendriesch)

  Show actual long-running query in query_time output
    (Peter Eisentraut)

  Add explicit ORDER BY to the slony_status check to get the most lagged server.
    (Jeff Frost)

  Improved multi-slave support in replicate_row.
    (Andrew Yochum)

  Change the way tables are quoted in replicate_row.
    (Glyn Astill)

  Don't swallow space before the -c flag when reporting errors
    (Jeff Janes)

  Fix and extend hot_standby_delay documentation
    (Michael Renner)

  Declare POD encoding to be utf8.
    (Christoph Berg)

=item B<Version 2.21.0> September 24, 2013

  Fix issue with SQL steps in check_pgagent_jobs for sql steps which perform deletes
    (Rob Emery via github pull)

  Install man page in section 1.
    (Peter Eisentraut, bug 53, github issue 26)

  Order lock types in check_locks output to make the ordering predictable;
  setting SKIP_NETWORK_TESTS will skip the new_version tests; other minor test
  suite fixes.
    (Christoph Berg)

  Fix same_schema check on 9.3 by ignoring relminmxid differences in pg_class
    (Christoph Berg)

=item B<Version 2.20.1> June 24, 2013

  Make connection check failures return CRITICAL not UNKNOWN
    (Dominic Hargreaves)

  Fix --reverse option when using string comparisons in custom queries
    (Nathaniel Waisbrot)

  Compute correct 'totalwastedbytes' in the bloat query
    (Michael Renner)

  Do not use pg_stats "inherited" column in bloat query, if the
    database is 8.4 or older. (Greg Sabino Mullane, per bug 121)

  Remove host reordering in hot_standby_delay check
    (Josh Williams, with help from Jacobo Blasco)

  Better output for the "simple" flag
    (Greg Sabino Mullane)

  Force same_schema to ignore the 'relallvisible' column
    (Greg Sabino Mullane)


=item B<Version 2.20.0> March 13, 2013

  Add check for pgagent jobs (David E. Wheeler)

  Force STDOUT to use utf8 for proper output
    (Greg Sabino Mullane; reported by Emmanuel Lesouef)

  Fixes for Postgres 9.2: new pg_stat_activity view,
    and use pg_tablespace_location, (Josh Williams)

  Allow for spaces in item lists when doing same_schema.

  Allow txn_idle to work again for < 8.3 servers by switching to query_time.

  Fix the check_bloat SQL to take inherited tables into account,
    and assume 2k for non-analyzed columns. (Geert Pante)

  Cache sequence information to speed up same_schema runs.

  Fix --excludeuser in check_txn_idle (Mika Eloranta)

  Fix user clause handling in check_txn_idle (Michael van Bracht)

  Adjust docs to show colon as a better separator inside args for locks
    (Charles Sprickman)

  Fix undefined $SQL2 error in check_txn_idle [github issue 16] (Patric Bechtel)

  Prevent "uninitialized value" warnings when showing the port (Henrik Ahlgren)

  Do not assume everyone has a HOME [github issue 23]

=item B<Version 2.19.0> January 17, 2012

  Add the --assume-prod option (Cédric Villemain)

  Add the cluster_id check (Cédric Villemain)

  Improve settings_checksum and checkpoint tests (Cédric Villemain)

  Do not do an inner join to pg_user when checking database size
    (Greg Sabino Mullane; reported by Emmanuel Lesouef)

  Use the full path when getting sequence information for same_schema.
    (Greg Sabino Mullane; reported by Cindy Wise)

  Fix the formula for calculating xlog positions (Euler Taveira de Oliveira)

  Better ordering of output for bloat check - make indexes as important
    as tables (Greg Sabino Mullane; reported by Jens Wilke)

  Show the dbservice if it was used at top of same_schema output
    (Mike Blackwell)

  Better installation paths (Greg Sabino Mullane, per bug 53)

=item B<Version 2.18.0> October 2, 2011

  Redo the same_schema action. Use new --filter argument for all filtering.
  Allow comparisons between any number of databases.
  Remove the dbname2, dbport2, etc. arguments.
  Allow comparison of the same db over time.

  Swap db1 and db2 if the slave is 1 for the hot standby check (David E. Wheeler)

  Allow multiple --schema arguments for the slony_status action (GSM and Jehan-Guillaume de Rorthais)

  Fix ORDER BY in the last vacuum/analyze action (Nicolas Thauvin)

  Fix check_hot_standby_delay perfdata output (Nicolas Thauvin)

  Look in the correct place for the .ready files with the archive_ready action (Nicolas Thauvin)

  New action: commitratio (Guillaume Lelarge)

  New action: hitratio (Guillaume Lelarge)

  Make sure --action overrides the symlink naming trick.

  Set defaults for archive_ready and wal_files (Thomas Guettler, GSM)

  Better output for wal_files and archive_ready (GSM)

  Fix warning when client_port set to empty string (bug #79)

  Account for "empty row" in -x output (i.e. source of functions).

  Fix some incorrectly named data fields (Andy Lester)

  Expand the number of pgbouncer actions (Ruslan Kabalin)

  Give detailed information and refactor txn_idle, txn_time, and query_time
    (Per request from bug #61)

  Set maxalign to 8 in the bloat check if box identified as '64-bit'
    (Michel Sijmons, bug #66)

  Support non-standard version strings in the bloat check.
    (Michel Sijmons and Gurjeet Singh, bug #66)

  Do not show excluded databases in some output (Ruslan Kabalin)

  Allow "and", "or" inside arguments (David E. Wheeler)

  Add the "new_version_box" action.

  Fix psql version regex (Peter Eisentraut, bug #69)

  Add the --assume-standby-mode option (Ruslan Kabalin)

  Note that txn_idle and query_time require 8.3 (Thomas Guettler)

  Standardize and clean up all perfdata output (bug #52)

  Exclude "idle in transaction" from the query_time check (bug #43)

  Fix the perflimit for the bloat action (bug #50)

  Clean up the custom_query action a bit.

  Fix space in perfdata for hot_standby_delay action (Nicolas Thauvin)

  Handle undef percents in check_fsm_relations (Andy Lester)

  Fix typo in dbstats action (Stas Vitkovsky)

  Fix MRTG for last vacuum and last_analyze actions.

=item B<Version 2.17.0> no public release

=item B<Version 2.16.0> January 20, 2011

  Add new action 'hot_standby_delay' (Nicolas Thauvin)
  Add cache-busting for the version-grabbing utilities.
  Fix problem with going to next method for new_version_pg
    (Greg Sabino Mullane, reported by Hywel Mallett in bug #65)
  Allow /usr/local/etc as an alternative location for the 
    check_postgresrc file (Hywel Mallett)
  Do not use tgisconstraint in same_schema if Postgres >= 9
    (Guillaume Lelarge)

=item B<Version 2.15.4> January 3, 2011

  Fix warning when using symlinks
    (Greg Sabino Mullane, reported by Peter Eisentraut in bug #63)

=item B<Version 2.15.3> December 30, 2010

  Show OK for no matching txn_idle entries.

=item B<Version 2.15.2> December 28, 2010

  Better formatting of sizes in the bloat action output.

  Remove duplicate perfs in bloat action output.

=item B<Version 2.15.1> December 27, 2010

  Fix problem when examining items in pg_settings (Greg Sabino Mullane)

  For connection test, return critical, not unknown, on FATAL errors
    (Greg Sabino Mullane, reported by Peter Eisentraut in bug #62)

=item B<Version 2.15.0> November 8, 2010

  Add --quiet argument to suppress output on OK Nagios results
  Add index comparison for same_schema (Norman Yamada and Greg Sabino Mullane)
  Use $ENV{PGSERVICE} instead of "service=" to prevent problems (Guillaume Lelarge)
  Add --man option to show the entire manual. (Andy Lester)
  Redo the internal run_command() sub to use -x and hashes instead of regexes.
  Fix error in custom logic (Andreas Mager)
  Add the "pgbouncer_checksum" action (Guillaume Lelarge)
  Fix regex to work on WIN32 for check_fsm_relations and check_fsm_pages (Luke Koops)
  Don't apply a LIMIT when using --exclude on the bloat action (Marti Raudsepp)
  Change the output of query_time to show pid,user,port, and address (Giles Westwood)
  Fix to show database properly when using slony_status (Guillaume Lelarge)
  Allow warning items for same_schema to be comma-separated (Guillaume Lelarge)
  Constraint definitions across Postgres versions match better in same_schema.
  Work against "EnterpriseDB" databases (Sivakumar Krishnamurthy and Greg Sabino Mullane)
  Separate perfdata with spaces (Jehan-Guillaume (ioguix) de Rorthais)
  Add new action "archive_ready" (Jehan-Guillaume (ioguix) de Rorthais)

=item B<Version 2.14.3> (March 1, 2010)

  Allow slony_status action to handle more than one slave.
  Use commas to separate function args in same_schema output (Robert Treat)

=item B<Version 2.14.2> (February 18, 2010)

  Change autovac_freeze default warn/critical back to 90%/95% (Robert Treat)
  Put all items one-per-line for relation size actions if --verbose=1

=item B<Version 2.14.1> (February 17, 2010)

  Don't use $^T in logfile check, as script may be long-running
  Change the error string for the logfile action for easier exclusion
    by programs like tail_n_mail

=item B<Version 2.14.0> (February 11, 2010)

  Added the 'slony_status' action.
  Changed the logfile sleep from 0.5 to 1, as 0.5 gets rounded to 0 on some boxes!

=item B<Version 2.13.2> (February 4, 2010)

  Allow timeout option to be used for logtime 'sleep' time.

=item B<Version 2.13.2> (February 4, 2010)

  Show offending database for query_time action.
  Apply perflimit to main output for sequence action.
  Add 'noowner' option to same_schema action.
  Raise sleep timeout for logfile check to 15 seconds.

=item B<Version 2.13.1> (February 2, 2010)

  Fix bug preventing column constraint differences from 2 > 1 for same_schema from being shown.
  Allow aliases 'dbname1', 'dbhost1', 'dbport1',etc.
  Added "nolanguage" as a filter for the same_schema option.
  Don't track "generic" table constraints (e.. $1, $2) using same_schema

=item B<Version 2.13.0> (January 29, 2010)

  Allow "nofunctions" as a filter for the same_schema option.
  Added "noperm" as a filter for the same_schema option.
  Ignore dropped columns when considered positions for same_schema (Guillaume Lelarge)

=item B<Version 2.12.1> (December 3, 2009)

  Change autovac_freeze default warn/critical from 90%/95% to 105%/120% (Marti Raudsepp)

=item B<Version 2.12.0> (December 3, 2009)

  Allow the temporary directory to be specified via the "tempdir" argument,
    for systems that need it (e.g. /tmp is not owned by root).
  Fix so old versions of Postgres (< 8.0) use the correct default database (Giles Westwood)
  For "same_schema" trigger mismatches, show the attached table.
  Add the new_version_bc check for Bucardo version checking.
  Add database name to perf output for last_vacuum|analyze (Guillaume Lelarge)
  Fix for bloat action against old versions of Postgres without the 'block_size' param.

=item B<Version 2.11.1> (August 27, 2009)

  Proper Nagios output for last_vacuum|analyze actions. (Cédric Villemain)
  Proper Nagios output for locks action. (Cédric Villemain)
  Proper Nagios output for txn_wraparound action. (Cédric Villemain)
  Fix for constraints with embedded newlines for same_schema.
  Allow --exclude for all items when using same_schema.

=item B<Version 2.11.0> (August 23, 2009)

  Add Nagios perf output to the wal_files check (Cédric Villemain)
  Add support for .check_postgresrc, per request from Albe Laurenz.
  Allow list of web fetch methods to be changed with the --get_method option.
  Add support for the --language argument, which overrides any ENV.
  Add the --no-check_postgresrc flag.
  Ensure check_postgresrc options are completely overridden by command-line options.
  Fix incorrect warning > critical logic in replicate_rows (Glyn Astill)

=item B<Version 2.10.0> (August 3, 2009)

  For same_schema, compare view definitions, and compare languages.
  Make script into a global executable via the Makefile.PL file.
  Better output when comparing two databases.
  Proper Nagios output syntax for autovac_freeze and backends checks (Cédric Villemain)

=item B<Version 2.9.5> (July 24, 2009)

  Don't use a LIMIT in check_bloat if --include is used. Per complaint from Jeff Frost.

=item B<Version 2.9.4> (July 21, 2009)

  More French translations (Guillaume Lelarge)

=item B<Version 2.9.3> (July 14, 2009)

  Quote dbname in perf output for the backends check. (Davide Abrigo)
  Add 'fetch' as an alternative method for new_version checks, as this 
    comes by default with FreeBSD. (Hywel Mallett)

=item B<Version 2.9.2> (July 12, 2009)

  Allow dots and dashes in database name for the backends check (Davide Abrigo)
  Check and display the database for each match in the bloat check (Cédric Villemain)
  Handle 'too many connections' FATAL error in the backends check with a critical,
    rather than a generic error (Greg, idea by Jürgen Schulz-Brüssel)
  Do not allow perflimit to interfere with exclusion rules in the vacuum and 
    analyze tests. (Greg, bug reported by Jeff Frost)

=item B<Version 2.9.1> (June 12, 2009)

  Fix for multiple databases with the check_bloat action (Mark Kirkwood)
  Fixes and improvements to the same_schema action (Jeff Boes)
  Write tests for same_schema, other minor test fixes (Jeff Boes)

=item B<Version 2.9.0> (May 28, 2009)

  Added the same_schema action (Greg)

=item B<Version 2.8.1> (May 15, 2009)

  Added timeout via statement_timeout in addition to perl alarm (Greg)

=item B<Version 2.8.0> (May 4, 2009)

  Added internationalization support (Greg)
  Added the 'disabled_triggers' check (Greg)
  Added the 'prepared_txns' check (Greg)
  Added the 'new_version_cp' and 'new_version_pg' checks (Greg)
  French translations (Guillaume Lelarge)
  Make the backends search return ok if no matches due to inclusion rules,
    per report by Guillaume Lelarge (Greg)
  Added comprehensive unit tests (Greg, Jeff Boes, Selena Deckelmann)
  Make fsm_pages and fsm_relations handle 8.4 servers smoothly. (Greg)
  Fix missing 'upd' field in show_dbstats (Andras Fabian)
  Allow ENV{PGCONTROLDATA} and ENV{PGBINDIR}. (Greg)
  Add various Perl module infrastructure (e.g. Makefile.PL) (Greg)
  Fix incorrect regex in txn_wraparound (Greg)
  For txn_wraparound: consistent ordering and fix duplicates in perf output (Andras Fabian)
  Add in missing exabyte regex check (Selena Deckelmann)
  Set stats to zero if we bail early due to USERWHERECLAUSE (Andras Fabian)
  Add additional items to dbstats output (Andras Fabian)
  Remove --schema option from the fsm_ checks. (Greg Mullane and Robert Treat)
  Handle case when ENV{PGUSER} is set. (Andy Lester)
  Many various fixes. (Jeff Boes)
  Fix --dbservice: check version and use ENV{PGSERVICE} for old versions (Cédric Villemain)

=item B<Version 2.7.3> (February 10, 2009)

  Make the sequence action check if sequence being used for a int4 column and
  react appropriately. (Michael Glaesemann)

=item B<Version 2.7.2> (February 9, 2009)

  Fix to prevent multiple groupings if db arguments given.

=item B<Version 2.7.1> (February 6, 2009)

  Allow the -p argument for port to work again.

=item B<Version 2.7.0> (February 4, 2009)

  Do not require a connection argument, but use defaults and ENV variables when 
    possible: PGHOST, PGPORT, PGUSER, PGDATABASE.

=item B<Version 2.6.1> (February 4, 2009)

  Only require Date::Parse to be loaded if using the checkpoint action.

=item B<Version 2.6.0> (January 26, 2009)

  Add the 'checkpoint' action.

=item B<Version 2.5.4> (January 7, 2009)

  Better checking of $opt{dbservice} structure (Cédric Villemain)
  Fix time display in timesync action output (Selena Deckelmann)
  Fix documentation typos (Josh Tolley)

=item B<Version 2.5.3> (December 17, 2008)

  Minor fix to regex in verify_version (Lee Jensen)

=item B<Version 2.5.2> (December 16, 2008)

  Minor documentation tweak.

=item B<Version 2.5.1> (December 11, 2008)

  Add support for --noidle flag to prevent backends action from counting idle processes.
  Patch by Selena Deckelmann.

  Fix small undefined warning when not using --dbservice.

=item B<Version 2.5.0> (December 4, 2008)

  Add support for the pg_Service.conf file with the --dbservice option.

=item B<Version 2.4.3> (November 7, 2008)

  Fix options for replicate_row action, per report from Jason Gordon.

=item B<Version 2.4.2> (November 6, 2008)

  Wrap File::Temp::cleanup() calls in eval, in case File::Temp is an older version.
  Patch by Chris Butler.

=item B<Version 2.4.1> (November 5, 2008)

  Cast numbers to numeric to support sequences ranges > bigint in check_sequence action.
  Thanks to Scott Marlowe for reporting this.

=item B<Version 2.4.0> (October 26, 2008)

 Add Cacti support with the dbstats action.
 Pretty up the time output for last vacuum and analyze actions.
 Show the percentage of backends on the check_backends action.

=item B<Version 2.3.10> (October 23, 2008)

 Fix minor warning in action check_bloat with multiple databases.
 Allow warning to be greater than critical when using the --reverse option.
 Support the --perflimit option for the check_sequence action.

=item B<Version 2.3.9> (October 23, 2008)

 Minor tweak to way we store the default port.

=item B<Version 2.3.8> (October 21, 2008)

 Allow the default port to be changed easily.
 Allow transform of simple output by MB, GB, etc.

=item B<Version 2.3.7> (October 14, 2008)

 Allow multiple databases in 'sequence' action. Reported by Christoph Zwerschke.

=item B<Version 2.3.6>  (October 13, 2008)

 Add missing $schema to check_fsm_pages. (Robert Treat)

=item B<Version 2.3.5> (October 9, 2008)

 Change option 'checktype' to 'valtype' to prevent collisions with -c[ritical]
 Better handling of errors.

=item B<Version 2.3.4> (October 9, 2008)

 Do explicit cleanups of the temp directory, per problems reported by sb@nnx.com.

=item B<Version 2.3.3> (October 8, 2008)

 Account for cases where some rounding queries give -0 instead of 0.
 Thanks to Glyn Astill for helping to track this down.

=item B<Version 2.3.2> (October 8, 2008)

 Always quote identifiers in check_replicate_row action.

=item B<Version 2.3.1> (October 7, 2008)

 Give a better error if one of the databases cannot be reached.

=item B<Version 2.3.0> (October 4, 2008)

 Add the "sequence" action, thanks to Gavin M. Roy for the idea.
 Fix minor problem with autovac_freeze action when using MRTG output.
 Allow output argument to be case-insensitive.
 Documentation fixes.

=item B<Version 2.2.4> (October 3, 2008)

 Fix some minor typos

=item B<Version 2.2.3> (October 1, 2008)

 Expand range of allowed names for --repinfo argument (Glyn Astill)
 Documentation tweaks.

=item B<Version 2.2.2> (September 30, 2008)

 Fixes for minor output and scoping problems.

=item B<Version 2.2.1> (September 28, 2008)

 Add MRTG output to fsm_pages and fsm_relations.
 Force error messages to one-line for proper Nagios output.
 Check for invalid prereqs on failed command. From conversations with Euler Taveira de Oliveira.
 Tweak the fsm_pages formula a little.

=item B<Version 2.2.0> (September 25, 2008)

 Add fsm_pages and fsm_relations actions. (Robert Treat)

=item B<Version 2.1.4> (September 22, 2008)

 Fix for race condition in txn_time action.
 Add --debugoutput option.

=item B<Version 2.1.3> (September 22, 2008)

 Allow alternate arguments "dbhost" for "host" and "dbport" for "port".
 Output a zero as default value for second line of MRTG output.

=item B<Version 2.1.2> (July 28, 2008)

 Fix sorting error in the "disk_space" action for non-Nagios output.
 Allow --simple as a shortcut for --output=simple.

=item B<Version 2.1.1> (July 22, 2008)

 Don't check databases with datallowconn false for the "autovac_freeze" action.

=item B<Version 2.1.0> (July 18, 2008)

 Add the "autovac_freeze" action, thanks to Robert Treat for the idea and design.
 Put an ORDER BY on the "txn_wraparound" action.

=item B<Version 2.0.1> (July 16, 2008)

 Optimizations to speed up the "bloat" action quite a bit.
 Fix "version" action to not always output in mrtg mode.

=item B<Version 2.0.0> (July 15, 2008)

 Add support for MRTG and "simple" output options.
 Many small improvements to nearly all actions.

=item B<Version 1.9.1> (June 24, 2008)

 Fix an error in the bloat SQL in 1.9.0
 Allow percentage arguments to be over 99%
 Allow percentages in the bloat --warning and --critical (thanks to Robert Treat for the idea)

=item B<Version 1.9.0> (June 22, 2008)

 Don't include information_schema in certain checks. (Jeff Frost)
 Allow --include and --exclude to use schemas by using a trailing period.

=item B<Version 1.8.5> (June 22, 2008)

 Output schema name before table name where appropriate.
 Thanks to Jeff Frost.

=item B<Version 1.8.4> (June 19, 2008)

 Better detection of problems in --replicate_row.

=item B<Version 1.8.3> (June 18, 2008)

 Fix 'backends' action: there may be no rows in pg_stat_activity, so run a second
   query if needed to find the max_connections setting.
 Thanks to Jeff Frost for the bug report.

=item B<Version 1.8.2> (June 10, 2008)

 Changes to allow working under Nagios' embedded Perl mode. (Ioannis Tambouras)

=item B<Version 1.8.1> (June 9, 2008)

 Allow 'bloat' action to work on Postgres version 8.0.
 Allow for different commands to be run for each action depending on the server version.
 Give better warnings when running actions not available on older Postgres servers.

=item B<Version 1.8.0> (June 3, 2008)

 Add the --reverse option to the custom_query action.

=item B<Version 1.7.1> (June 2, 2008)

 Fix 'query_time' action: account for race condition in which zero rows appear in pg_stat_activity.
 Thanks to Dustin Black for the bug report.

=item B<Version 1.7.0> (May 11, 2008)

 Add --replicate_row action

=item B<Version 1.6.1> (May 11, 2008)

 Add --symlinks option as a shortcut to --action=rebuild_symlinks

=item B<Version 1.6.0> (May 11, 2008)

 Add the custom_query action.

=item B<Version 1.5.2> (May 2, 2008)

 Fix problem with too eager creation of custom pgpass file.

=item B<Version 1.5.1> (April 17, 2008)

 Add example Nagios configuration settings (Brian A. Seklecki)

=item B<Version 1.5.0> (April 16, 2008)

 Add the --includeuser and --excludeuser options. Documentation cleanup.

=item B<Version 1.4.3> (April 16, 2008)

 Add in the 'output' concept for future support of non-Nagios programs.

=item B<Version 1.4.2> (April 8, 2008)

 Fix bug preventing --dbpass argument from working (Robert Treat).

=item B<Version 1.4.1> (April 4, 2008)

 Minor documentation fixes.

=item B<Version 1.4.0> (April 2, 2008)

 Have 'wal_files' action use pg_ls_dir (idea by Robert Treat).
 For last_vacuum and last_analyze, respect autovacuum effects, add separate 
   autovacuum checks (ideas by Robert Treat).

=item B<Version 1.3.1> (April 2, 2008)

 Have txn_idle use query_start, not xact_start.

=item B<Version 1.3.0> (March 23, 2008)

 Add in txn_idle and txn_time actions.

=item B<Version 1.2.0> (February 21, 2008)

 Add the 'wal_files' action, which counts the number of WAL files
   in your pg_xlog directory.
 Fix some typos in the docs.
 Explicitly allow -v as an argument.
 Allow for a null syslog_facility in the 'logfile' action.

=item B<Version 1.1.2> (February 5, 2008)

 Fix error preventing --action=rebuild_symlinks from working.

=item B<Version 1.1.1> (February 3, 2008)

 Switch vacuum and analyze date output to use 'DD', not 'D'. (Glyn Astill)

=item B<Version 1.1.0> (December 16, 2008)

 Fixes, enhancements, and performance tracking.
 Add performance data tracking via --showperf and --perflimit
 Lots of refactoring and cleanup of how actions handle arguments.
 Do basic checks to figure out syslog file for 'logfile' action.
 Allow for exact matching of beta versions with 'version' action.
 Redo the default arguments to only populate when neither 'warning' nor 'critical' is provided.
 Allow just warning OR critical to be given for the 'timesync' action.
 Remove 'redirect_stderr' requirement from 'logfile' due to 8.3 changes.
 Actions 'last_vacuum' and 'last_analyze' are 8.2 only (Robert Treat)

=item B<Version 1.0.16> (December 7, 2007)

 First public release, December 2007

=back

=head1 BUGS AND LIMITATIONS

The index bloat size optimization is rough.

Some actions may not work on older versions of Postgres (before 8.0).

Please report any problems to check_postgres@bucardo.org

=head1 AUTHOR

Greg Sabino Mullane <greg@endpoint.com>


=head1 NAGIOS EXAMPLES

Some example Nagios configuration settings using this script:

 define command {
     command_name    check_postgres_size
     command_line    $USER2$/check_postgres.pl -H $HOSTADDRESS$ -u pgsql -db postgres --action database_size -w $ARG1$ -c $ARG2$
 }

 define command {
     command_name    check_postgres_locks
     command_line    $USER2$/check_postgres.pl -H $HOSTADDRESS$ -u pgsql -db postgres --action locks -w $ARG1$ -c $ARG2$
 }


 define service {
     use                    generic-other
     host_name              dbhost.gtld
     service_description    dbhost PostgreSQL Service Database Usage Size
     check_command          check_postgres_size!256000000!512000000
 }

 define service {
     use                    generic-other
     host_name              dbhost.gtld
     service_description    dbhost PostgreSQL Service Database Locks
     check_command          check_postgres_locks!2!3
 }

=head1 LICENSE AND COPYRIGHT

Copyright (c) 2007-2015 Greg Sabino Mullane <greg@endpoint.com>.

Redistribution and use in source and binary forms, with or without 
modification, are permitted provided that the following conditions are met:

  1. Redistributions of source code must retain the above copyright notice, 
     this list of conditions and the following disclaimer.
  2. Redistributions in binary form must reproduce the above copyright notice, 
     this list of conditions and the following disclaimer in the documentation 
     and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE AUTHOR "AS IS" AND ANY EXPRESS OR IMPLIED 
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF 
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO 
EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT 
OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS 
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN 
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING 
IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY 
OF SUCH DAMAGE.

=cut

# vi: tabstop=4 shiftwidth=4 expandtab
