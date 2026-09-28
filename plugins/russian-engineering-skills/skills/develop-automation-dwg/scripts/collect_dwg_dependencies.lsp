(vl-load-com)
(setvar "FILEDIA" 0)
(setvar "CMDDIA" 0)

(setq outPath (getenv "DWG_DEP_REPORT"))
(if (or (null outPath) (= outPath ""))
  (setq outPath (strcat (getvar "TEMPPREFIX") "dwg_dependencies.tsv"))
)
(setq fh (open outPath "w"))

(defun emit (kind name raw resolved)
  (write-line
    (strcat kind "\t" (if name name "") "\t" (if raw raw "") "\t"
            (if resolved resolved ""))
    fh
  )
)

(defun resolved-file (p)
  (cond
    ((or (null p) (= p "")) "")
    ((findfile p) (findfile p))
    (T "")
  )
)

(emit "ROOT_DWG" (getvar "DWGNAME")
      (strcat (getvar "DWGPREFIX") (getvar "DWGNAME"))
      (strcat (getvar "DWGPREFIX") (getvar "DWGNAME")))

(setq rec (tblnext "STYLE" T))
(while rec
  (setq styleName (cdr (assoc 2 rec)))
  (setq fontFile (cdr (assoc 3 rec)))
  (setq bigFont (cdr (assoc 4 rec)))
  (emit "FONT" styleName fontFile (resolved-file fontFile))
  (if (and bigFont (/= bigFont ""))
    (emit "BIGFONT" styleName bigFont (resolved-file bigFont))
  )
  (setq rec (tblnext "STYLE"))
)

(setq rec (tblnext "BLOCK" T))
(while rec
  (setq flags (cdr (assoc 70 rec)))
  (if (and flags (/= 0 (logand flags 4)))
    (progn
      (setq xrefPath (cdr (assoc 1 rec)))
      (emit "XREF" (cdr (assoc 2 rec)) xrefPath (resolved-file xrefPath))
    )
  )
  (setq rec (tblnext "BLOCK"))
)

(setq layoutRec (dictsearch (namedobjdict) "ACAD_LAYOUT"))
(if layoutRec
  (progn
    (setq layoutDict (cdr (assoc -1 layoutRec)))
    (setq layItem (dictnext layoutDict T))
    (while layItem
      (setq layName (cdr (assoc 1 layItem)))
      (setq pc3 (cdr (assoc 2 layItem)))
      (setq ctb (cdr (assoc 7 layItem)))
      (if (and pc3 (/= pc3 ""))
        (emit "PLOTTER" layName pc3 (resolved-file pc3))
      )
      (if (and ctb (/= ctb ""))
        (emit "PLOTSTYLE" layName ctb (resolved-file ctb))
      )
      (setq layItem (dictnext layoutDict))
    )
  )
)

(foreach dictName '("ACAD_IMAGE_DICT" "ACAD_PDFDEFINITIONS"
                    "ACAD_DWFDEFINITIONS" "ACAD_DGNDEFINITIONS")
  (setq dictRec (dictsearch (namedobjdict) dictName))
  (if dictRec
    (progn
      (setq dictEnt (cdr (assoc -1 dictRec)))
      (setq item (dictnext dictEnt T))
      (while item
        (setq itemName (cdr (assoc 3 item)))
        (setq itemPath (cdr (assoc 1 item)))
        (if itemPath
          (emit "UNDERLAY_OR_IMAGE" itemName itemPath
                (resolved-file itemPath))
        )
        (setq item (dictnext dictEnt))
      )
    )
  )
)

(close fh)
(princ (strcat "\nDWG_DEPENDENCY_REPORT=" outPath))
(princ)
