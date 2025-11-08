-- Auto-generated History Inserts

-- Original Query

update

-- Auto-generated History Inserts

INSERT INTO DatafixHistory
(hycrm, sTableName, sColumnName, hForeignKey, sNotes, sNewValue, sOldValue, dtDate)
VALUES
(select '123456', 'trans', 'stotalamount', hmy, 'updated trans', 12342, stotalamount, GETDATE() from trans where hmy = 700000223);

INSERT INTO DatafixHistory
(hycrm, sTableName, sColumnName, hForeignKey, sNotes, sNewValue, sOldValue, dtDate)
VALUES
(select '123456', 'trans', 'spaidamount', hmy, 'updated trans', 12343, spaidamount, GETDATE() from trans where hmy = 700000223);

-- Original Query

update trans set stotalamount = 12342, spaidamount = 12343 where hmy = 700000223

-- Auto-generated History Inserts

-- Original Query

update

-- Auto-generated History Inserts

INSERT INTO DatafixHistory
(hycrm, sTableName, sColumnName, hForeignKey, sNotes, sNewValue, sOldValue, dtDate)
VALUES
(select '123456', 'detail', 'hchkorchg', hmy, 'updated detail', 700001232, hchkorchg, GETDATE() from detail where hmy in (12312,1111) and itype=3);

-- Original Query

update detail set hchkorchg = 700001232 where hmy in (12312,1111) and itype=3

-- Auto-generated History Insert

INSERT INTO DatafixHistory
(hycrm, sTableName, sColumnName, hForeignKey, sNotes, sNewValue, sOldValue, dtDate)
VALUES
(select '123456', 'UnknownTable', '', hmy, 'delete UnknownTable', '', '', GETDATE() from UnknownTable where 1=1);

-- Backup Before Delete

SELECT * INTO case#123456_UnknownTable FROM UnknownTable where 1=1;

-- Original Query

delete

-- Auto-generated History Insert

INSERT INTO DatafixHistory
(hycrm, sTableName, sColumnName, hForeignKey, sNotes, sNewValue, sOldValue, dtDate)
VALUES
(select '123456', 'trans', '', hmy, 'delete trans', '', '', GETDATE() from trans where hmy = 46842154854);

-- Backup Before Delete

SELECT * INTO case#123456_trans FROM trans where hmy = 46842154854;

-- Original Query

delete from trans where hmy = 46842154854

-- Auto-generated History Inserts

-- Original Query

UPDATE

-- Auto-generated History Inserts

INSERT INTO DatafixHistory
(hycrm, sTableName, sColumnName, hForeignKey, sNotes, sNewValue, sOldValue, dtDate)
VALUES
(select '123456', 'listprop', 'ct.hCommICS', hmy, 'updated listprop', CASE  WHEN ct.hLeaseType IN (1, 6, 15) THEN 1  WHEN ct.hLeaseType IN (8,13) THEN 2  WHEN ct.hLeaseType = 5 THEN 3  WHEN ct.hLeaseType = 11 THEN 4  WHEN ct.hLeaseType = 2 THEN 5  WHEN ct.hLeaseType = 10 THEN 9  ELSE ct.hCommICS  END FROM CommTenant ct INNER JOIN Tenant t ON t.hmyperson = ct.htenant and t.istatus in (0) INNER JOIN Property p ON p.hmy = t.hProperty and p.itype=3 WHERE t.hproperty IN (  SELECT hproperty, ct.hCommICS, GETDATE() from listprop where hproplist = 2688 ));

-- Original Query

UPDATE ct SET ct.hCommICS =  CASE  WHEN ct.hLeaseType IN (1, 6, 15) THEN 1  WHEN ct.hLeaseType IN (8,13) THEN 2  WHEN ct.hLeaseType = 5 THEN 3  WHEN ct.hLeaseType = 11 THEN 4  WHEN ct.hLeaseType = 2 THEN 5  WHEN ct.hLeaseType = 10 THEN 9  ELSE ct.hCommICS  END FROM CommTenant ct INNER JOIN Tenant t ON t.hmyperson = ct.htenant and t.istatus in (0) INNER JOIN Property p ON p.hmy = t.hProperty and p.itype=3 WHERE t.hproperty IN (  SELECT hproperty  FROM listprop  WHERE hproplist = 2688 )