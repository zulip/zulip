
; Move automatic backups into a directory off to the side
(defvar backup-dir "~/.emacs-backups/")
(setq backup-directory-alist (list (cons "." backup-dir)))
