(setq out (open "C:/Temp/dwg_publish_work/inserts.txt" "w"))
; Set source layout before use.
(setq srcLayout "Лист1")
(setq ss (ssget "X" (list (cons 410 srcLayout) (cons 0 "INSERT"))))
(if ss
  (progn
    (setq i 0)
    (while (< i (sslength ss))
      (setq d (entget (ssname ss i)))
      (setq name (cdr (assoc 2 d)))
      (setq p (cdr (assoc 10 d)))
      (setq sx (cdr (assoc 41 d)))
      (setq sy (cdr (assoc 42 d)))
      (setq rot (cdr (assoc 50 d)))
      (write-line
        (strcat
          "name=" name
          "\tx=" (rtos (car p) 2 4)
          "\ty=" (rtos (cadr p) 2 4)
          "\tsx=" (rtos (if sx sx 1.0) 2 4)
          "\tsy=" (rtos (if sy sy 1.0) 2 4)
          "\trot=" (rtos (if rot rot 0.0) 2 4)
        )
        out
      )
      (setq i (1+ i))
    )
  )
)
(close out)
(princ "\nDUMP_INSERTS_DONE")
(princ)
