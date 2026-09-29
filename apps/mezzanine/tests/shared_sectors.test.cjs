const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const template = fs.readFileSync(path.join(__dirname, '..', 'dashboard_template.html'), 'utf8');
const helpers = template.slice(template.indexOf('async function fetchPaged('), template.indexOf('async function hydrateFundReturnHistory('));
const holdings = [
  {code:'CB19',underlyingCode:'032820',sectorCode:'032820',sector:'old'},
  {code:'CB20',underlyingCode:'032820',sectorCode:'032820',sector:'미분류'},
  {code:'EB',underlyingCode:'005930',sectorCode:'005930',sector:'old'},
  {code:'MISSING',underlyingCode:'019010',sector:'old'},
  {code:'LEGACY',underlyingCode:'134580',sector:'old'},
  {code:'CALL',sectorCode:'032820',sector:'미분류'},
];
const records = [
  {'KR코드':'CB19','교환코드':'032820','교환대상명':'우리기술'},
  {'KR코드':'CB20','교환코드':32820,'교환대상명':'우리기술'},
  {'KR코드':'EB','교환코드':'005930','발행코드':'019010','교환대상명':'삼성전자'},
  {'KR코드':'MISSING','교환코드':'','발행코드':'019010','교환대상명':'확인불가'},
  {'KR코드':'REFERENCE','교환코드':'134580','교환대상명':'탑코'},
  {'KR코드':'LEGACY','교환코드':'','교환대상명':'엔키홀딩스(구.탑코)'},
];
const metadata = [
  {'코드':'032820','업종(대)':'산업재','업종(중)':'산업재-자본재'},
  {'코드':'005930','업종(대)':'IT','업종(중)':'IT-반도체'},
  {'코드':'134580','업종(대)':'커뮤니케이션','업종(중)':'커뮤-미디어엔터'},
  {'코드':'019010','업종(대)':'경기소비재','업종(중)':'경기-유통'},
];
const securities = [{...holdings[1]}];
const context = {window:{MEZZ_DATA:{holdings,securities}}};
vm.createContext(context);
vm.runInContext(helpers, context);
let requestedCodes;
const client = {from(table){
  assert.equal(table,'manual_file_rows');
  return {
    select(){return this},
    eq(field,value){assert.ok((field==='domain'&&value==='stock')||(field==='file_key'&&value==='sector'));return this},
    in(field,codes){assert.equal(field,'payload->>코드');requestedCodes=Array.from(codes);return this},
    order(){return this},
    async range(){return {data:metadata.filter(p=>requestedCodes.includes(p['코드'])).map(payload=>({payload})),error:null}},
  };
}};
(async()=>{
  await context.hydrateSharedSectors(client,records);
  for(const row of [holdings[0],holdings[1],holdings[5],securities[0]]){
    assert.equal(row.sectorLarge,'산업재');assert.equal(row.sectorMid,'산업재-자본재');
  }
  assert.equal(holdings[2].sectorLarge,'IT');assert.equal(holdings[2].sectorMid,'IT-반도체');
  assert.equal(holdings[3].sectorLarge,'미분류');assert.equal(holdings[3].sectorCode,'');
  assert.ok(!requestedCodes.includes('019010'));
  assert.equal(holdings[4].sectorCode,'134580');assert.equal(holdings[4].sectorLarge,'커뮤니케이션');
  metadata[0]['업종(중)']='갱신된 중분류';
  await context.hydrateSharedSectors(client,records);
  assert.equal(holdings[1].sectorMid,'갱신된 중분류');
  console.log('Shared-sector refresh checks passed: same target, EB target, missing target, legacy name, call alias, metadata update.');
})().catch(error=>{console.error(error);process.exitCode=1});
