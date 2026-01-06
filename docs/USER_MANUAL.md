# USER MANUAL

## Uploading a VCF 
- Data persists between use, therefore use the upload button directly to see what has been previously uploaded.
- Further files can be uploaded by using the 'choose files' button. Multiple VCF files can be uploaded by holding 'Ctrl'.
![Choose file(s)](https://github.com/richard-gawne/ClinVar-annotator/blob/documentation_hk/docs/images/Choose_file.PNG)
![Selecting file(s)](https://github.com/richard-gawne/ClinVar-annotator/blob/documentation_hk/docs/images/Selecting_files.png)

- Click on 'Upload' to proceed. NOTE: files must be VCF format and variants called against GRCh38.
![Upload file(s)](https://github.com/richard-gawne/ClinVar-annotator/blob/documentation_hk/docs/images/Upload.PNG)

- NOTE: Annotation and table display may take up to 30 seconds for a VCF file with approximately 10 variants.

## Navigating the results page

### Multi-select Filters
![Multi-select filter](https://github.com/richard-gawne/ClinVar-annotator/blob/documentation_hk/docs/images/Multiselect_filter.png)

- There are 4 filter options that can be used to narrow down the results page: 
    - Patient 
    - Variant
    - Gene Symbol
    - Consensus Classification 
- Filters are dropdowns, so that multiple filters can be applied at any one time

### Search function
![Search function](https://github.com/richard-gawne/ClinVar-annotator/blob/documentation_hk/docs/images/Search.PNG)

- Filters can also be applied by using the search function. Any data point can be searched 
  to condense the table to show only the specified data points
- E.g. the gene 'SNCA' can be inputted so that only fields containing SNCA as the 
  gene symbol will be displayed.
- Additionally there are sorting arrows at the top of each column within the table (up for ascending and down for descending)

### Summary
![Table summary](https://github.com/richard-gawne/ClinVar-annotator/blob/documentation_hk/docs/images/Summary.png)

- The summary description provides information regarding what is currently shown within the table
- This includes the number of patients, variants, genes, and related classification
- This summary will change based on filters or searches applied

### Downloading a CSV
- Click on the 'download CSV' button to download a CSV based on filters and searches
- This can easily be visualised in notepad or Excel format (NOTE: star rating is not shown in Excel)

Notepad
![Notepad](https://github.com/richard-gawne/ClinVar-annotator/blob/documentation_hk/docs/images/Notepad.PNG)

Excel
![Excel](https://github.com/richard-gawne/ClinVar-annotator/blob/documentation_hk/docs/images/Excel.PNG)

