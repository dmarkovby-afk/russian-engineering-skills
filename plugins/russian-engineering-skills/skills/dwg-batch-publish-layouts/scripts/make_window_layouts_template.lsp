(setvar "FILEDIA" 0)
(setvar "CMDDIA" 0)
(setvar "BACKGROUNDPLOT" 0)

; Fill these for the current DWG.
(setq srcLayout "Лист1")
(setq report (open "C:/Temp/dwg_publish_work/make_window_layouts_report.txt" "w"))

; Frame format: left bottom right top source-block-or-note.
(setq frames
  (list
    ; (list 67.0837 2621.6240 488.0837 2918.6240 "A$C72c2bba3")
  )
)

(defun pad2 (n)
  (if (< n 10) (strcat "0" (itoa n)) (itoa n))
)

(defun setup-window-plot (layoutName left bottom right top / orient)
  (setq orient (if (> (- right left) (- top bottom)) "_L" "_P"))
  (setvar "CTAB" layoutName)
  (command "_.-PLOT"
    "_Y" layoutName "DWG To PDF.pc3" "" "_M" orient "_N"
    "_W"
    (strcat (rtos left 2 4) "," (rtos bottom 2 4))
    (strcat (rtos right 2 4) "," (rtos top 2 4))
    "_F" "_C" "_Y" "monochrome.ctb" "_Y" "_N" "_N" "_N"
    "" "_Y" "_N"
  )
)

(defun make-one (idx frame / name left bottom right top note)
  (setq name (strcat "Sheet_" (pad2 idx)))
  (setq left (nth 0 frame))
  (setq bottom (nth 1 frame))
  (setq right (nth 2 frame))
  (setq top (nth 3 frame))
  (setq note (nth 4 frame))
  (command "_.-LAYOUT" "_C" srcLayout name)
  (setup-window-plot name left bottom right top)
  (write-line
    (strcat name
      "\tnote=" note
      "\twindow=" (rtos left 2 4) "," (rtos bottom 2 4) " - " (rtos right 2 4) "," (rtos top 2 4)
      "\tsize=" (rtos (- right left) 2 4) "x" (rtos (- top bottom) 2 4)
    )
    report
  )
)

(setq i 1)
(foreach frame frames
  (make-one i frame)
  (setq i (1+ i))
)

(if frames (setvar "CTAB" "Sheet_01"))
(command "_.QSAVE")
(close report)
(princ "\nMAKE_WINDOW_LAYOUTS_DONE")
(princ)
