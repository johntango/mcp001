# SEC Edgartools 

Our goal is to understand the "state" of a company and calculate a "sentiment" score. 
To do this we will extract "events" from the data. 

Here is an overview of SEC data and what each Part and Item cover
| Part | Item | Description                            |
| ---- | ---- | -------------------------------------- |
| I    | 1    | Financial Statements                   |
| I    | 2    | MD\&A                                  |
| I    | 3    | Market Risk Disclosure (if required)   |
| I    | 4    | Controls and Procedures                |
| II   | 1    | Legal Proceedings                      |
| II   | 1A   | Risk Factors                           |
| II   | 2    | Unregistered Sales / Share Repurchases |
| II   | 3    | Defaults on Securities                 |
| II   | 4    | Mine Safety (if applicable)            |
| II   | 5    | Other Material Information             |
| II   | 6    | Exhibits and Certifications            |



| Category                  | Relevant SEC Forms and Items                                 |
| ------------------------- | ------------------------------------------------------------ |
| **Executive Changes**     | 8-K (Item 5.02)                                              |
| **Financial Updates**     | 10-K, 10-Q, 8-K (Item 2.02)                                  |
| **M\&A**                  | 8-K (Items 1.01, 2.01, 8.01), S-4, Schedule TO, Schedule 13D |
| **Litigation**            | 10-Q/K (Item 1/3), 8-K (Item 8.01)                           |
| **Bankruptcy**            | 8-K (Item 1.03)                                              |
| **Product Announcements** | 8-K (Item 8.01)                                              |
| **Regulatory Changes**    | 8-K (Item 8.01), 10-Q/K (Risk Factors, MD\&A)                |
