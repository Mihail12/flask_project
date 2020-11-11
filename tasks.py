import csv
from app import celery
from config import EIAS_BASE_URL, EIAS_POST_UPDATE_INACTIVE_ID_FR
from models import DocType, db, DocLostUpload, ReasonEnum
from schemas import DocLostCreateSchema
from utils import get_dep_by_code, request_to_passport, get_citizenship_by_name, \
    date_from_invalid_csv


@celery.task()
def save_docs_lost(doc_lost_upload_id):
    """
    завантаження файлів з недійсними документами через ВЕБ інтерфейс  #todo revrite
    :param doc_lost_upload_id: Результати обробки файла
    :return: у тому випадку коли celery False

        Справочник типов документов:
            IP =Паспорт громадянина України
            ID =Паспорт громадянина України у формі картки
            P =Паспорт громадянина України для виїзду за кордон
            IS =Посвідчення особи на повернення в Україну
            IT =Тимчасове посвідчення громадянина України
            IN =Посвідчення особи без громадянства для виїзду за кордон
            ER =Посвідка на постійне проживання
            ET =Посвідка на тимчасове проживання
            EG =Картка мігранта
            EY =Посвідчення біженця
            IB =Проїзний документ біженця
            ED =Посвідчення особи, яка потребує додаткового захисту
            SP =Проїзний документ особи, якій надано додатковий захист
            PR =Проїзний документ дитини

            Справочник статусов документов:
                001=Виданий
                002=Вилучений
                003=Тимчасово затриманий
                004=Анульований бланк
                005=Знищений
                400=Недійсний
                401=Недійсний у зв'язку із обміном на підставі зміни імені
                402=Недійсний - статус встановлено автоматично на підставі зміни імені
                403=Недійсний - встановлено розбіжності у записах
                404=Недійсний - непридатний до використання
                405=Недійсний у зв'язку з припиненням громадянства України
                406=Недійсний - викрадений
                407=Недійсний - втрачений
                408=Недійсний - померлої особи (незданий)
                409=Недійсний - оформлений з порушенням законодавства
                410=Недійсний - не отриманий власником протягом року
                411=Недійсний - відмова від отримання
                412=Недійсний - закінчився строк дії
                413=Недійсний - визнано за результатами розслідування
                414=Недійсний - технічно зіпсований
    """
    inactive = DocLostUpload.query.get(doc_lost_upload_id)

    error_list = []
    message = u''

    dict_doc_type_id = {'IP': DocType.ID, 'ID': DocType.ID, 'P': DocType.P, 'IS':  DocType.IS, 'IT': DocType.IT,
                        'IN': DocType.IN, 'ER': DocType.ER, 'ET': DocType.ET, 'EG': DocType.EG, 'EY': DocType.EY,
                        'SP': DocType.SP, 'IB': DocType.IB, 'ED': DocType.ED, 'PR': DocType.PR, 'AC': DocType.AC}

    dict_doc_reason_model = {'001': ReasonEnum.VALID.value,
                             '002': ReasonEnum.CANCELED.value,
                             '003': ReasonEnum.DETAINED.value,
                             '004': ReasonEnum.CANCELED_FORM.value,
                             '005': ReasonEnum.DESTROY.value,
                             '400': ReasonEnum.NOT_VALID.value,
                             '402': ReasonEnum.NOT_VALID.value,
                             '403': ReasonEnum.NOT_VALID.value,
                             '404': ReasonEnum.SPOIL.value,
                             '405': ReasonEnum.NOT_VALID.value,
                             '406': ReasonEnum.STOLEN.value,
                             '407': ReasonEnum.LOST.value,
                             '408': ReasonEnum.DECEASED.value,
                             '409': ReasonEnum.NOT_VALID.value,
                             '410': ReasonEnum.ISSUE_REF.value,
                             '411': ReasonEnum.ISSUE_REF.value,
                             '412': ReasonEnum.NOT_VALID.value,
                             '413': ReasonEnum.NOT_VALID.value,
                             '414': ReasonEnum.SPOIL_TECH.value
                             }

    fields_list = ['doc_type_id', 'series', 'number', 'reason_id', 'last_name', 'first_name', 'middle_name',
                   'date_birth', 'citizenship_id', 'issue_date', 'exp_date', 'dmsudep_issue_id',
                   'date_invalid', 'date_destruction', 'act', 'notes', 'unknown']

    log_file_list = []
    partial_file_list = []
    try:
        dictReader = csv.DictReader(open(inactive.file_upload, 'r'),
                                    fieldnames=fields_list, delimiter=';', quotechar='"')

        # lines = sum(1 for row in dictReader)

        for iteration, doc_lost_data in enumerate(dictReader, 1):
            doc_lost_line = ';'.join(value for key, value in doc_lost_data.items() if value is not None)
            doc_lost_data.pop('unknown', None)

            # process_percent = int(100 * float(iteration) / float(lines))
            # current_task.update_state(state='PROGRESS',  meta={'process_percent': process_percent})

            if (not doc_lost_data['doc_type_id'].upper() in dict_doc_type_id) or (not doc_lost_data['reason_id'] in dict_doc_reason_model):
                log_file_list.append(f'Помилка в рядку - {iteration} невірно вказано doc_type чи status')
                partial_file_list.append(doc_lost_line)
                continue
            if not (len(doc_lost_data['number']) == 9 and len(doc_lost_data['series']) == 0 \
                    or len(doc_lost_data['number']) == 6 and len(doc_lost_data['series']) == 2):
                message = u'Помилка в рядку -' + str(iteration) + u' серія чи номер не відповідає кількості ' \
                                                             u'символів чи серія має невідповідне кодування'
                log_file_list.append(message)
                partial_file_list.append(doc_lost_line)
                continue

            try:
                doc_schema = DocLostCreateSchema()
                data = {
                    "doc_type_id": dict_doc_type_id[doc_lost_data['doc_type_id'].upper()],
                    "series": doc_lost_data['series'].upper().strip(),
                    "number": doc_lost_data['number'].strip(),
                    "reason_id": dict_doc_reason_model[doc_lost_data['reason_id']],
                    "last_name": doc_lost_data['last_name'].upper(),
                    "first_name": doc_lost_data['first_name'].upper(),
                    "middle_name": doc_lost_data['middle_name'].upper(),
                    "date_birth": date_from_invalid_csv(doc_lost_data['date_birth']),
                    "citizenship_id": get_citizenship_by_name(doc_lost_data['citizenship_id'].upper()).get('id'),
                    "issue_date": date_from_invalid_csv(doc_lost_data['issue_date']),
                    "exp_date": date_from_invalid_csv(doc_lost_data['exp_date']),
                    "dmsudep_issue_id": get_dep_by_code(doc_lost_data['dmsudep_issue_id']).get('id'),
                    "date_invalid": date_from_invalid_csv(doc_lost_data['date_invalid']),
                    "date_destruction": date_from_invalid_csv(doc_lost_data['date_destruction']),
                    "act": doc_lost_data['act'],
                    "notes": doc_lost_data['notes'],
                    "user_add_id": inactive.user_add_id,
                    "dmsu_add_id": inactive.dmsu_add_id,
                }
                document = doc_schema.load(data=data)
                errors = doc_schema.validate(data)
                if errors:
                    log_file_list.append(f'Помилка в рядку - {iteration} {errors}')
                    partial_file_list.append(doc_lost_line)
                    continue

                db.session.add(document)
                db.session.commit()

                url = f'{EIAS_BASE_URL}{EIAS_POST_UPDATE_INACTIVE_ID_FR}'
                update_passport_data = {
                    "doc_type_id": document.doc_type_id,
                    "number": document.number,
                    "series": document.series,
                    "doc_status_id": document.reason_id,
                    "inactive_id": document.id,
                }
                request_to_passport(url, method='POST', data=update_passport_data)

            except:
                message = u'Помилка в рядку -' + str(iteration)
                log_file_list.append(message)
                partial_file_list.append(doc_lost_line)
                continue

    except csv.Error:
        message = u'дані в файлі не відповідають формату csv файлів'
        log_file_list.append(message)

    log_file_path = inactive.file_upload.replace('csv', 'log').replace('INACTIVE', 'ERROR_LOG')
    inactive.file_upload_log = log_file_path
    inactive.file_upload_partial = log_file_path
    db.session.add(inactive)
    db.session.commit()
    return message, error_list
