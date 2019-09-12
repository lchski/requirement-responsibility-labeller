Unhandled edge cases:

- 23601 (Standard on Web Accessibility): Responsible description isn’t in its own clause, but in the `title` attribute of a `section`: `<section anchor="6.1" title="6.1 Managers, functional specialists, and equivalents responsible for Web content or Web pages &#xA;&#xA;are responsible for:">` (also a problem in 25875, Standard on Web Interoperability)
- 23601 (Standard on Web Accessibility): Includes additional requirements in a “Monitoring and reporting requirements” section (chapter 7)
- 24227 (Standard on Web Usability): Responsible description is part of another clause (clause isn't properly split, occurs in a few spots in the policy): `6.1.8 Ensuring that websites and Web applications are optimized for mobile devices as described in the Technical Specifications for the Web and Mobile Presence . 6.2 Senior departmental officials, designated by the deputy head, are responsible for the following:` (also a problem in 27600, Standard on Email Management; 16553, Standard on Geospatial Data; 18909, Standard on Metadata)

Don't show up in the policy hierarchy:

```
12510,"Policy on Privacy Protection"
18309,"Directive on Privacy Practices"
18308,"Directive on Privacy Impact Assessment"
```

---

Sometimes you make responsibility signals that are really just for one policy, like this:

```
"designated senior executive",8,singular,
```

Written for the IM Roles Directive, this could accidentally cast too wide a net elsewhere. Options:

- Leave it as-is, looking to see the impact (does this IM actor show up where it shouldn't?)
- Point it away from the “Departmental Information Management Senior Official” actor, instead at a more generic senior official actor
- Refactor the responsibles code to account for policy-specific signals (cool, but more work!)

---

Check for hidden responsible actors, i.e., has “responsible” in `text` and `row` != `responsible_clause`