import { util } from '@aws-appsync/utils';

/**
 * Sends a request to the attached data source
 * @param {import('@aws-appsync/utils').Context} ctx the context
 * @returns {*} the request
 */
export function request(ctx) {
    const id = util.autoId(); 
    const createdAt = util.time.nowISO8601();

    return {
        operation: "PutItem",
        key: { id: { S: id } },
        attributeValues: {
            id: { S: id },
            userId: { N: ctx.args.userId.toString() },
            createdAt: { S: createdAt },
            payLoad: util.dynamodb.toMap(ctx.args.payLoad) 
        }
    };
}

/**
 * Returns the resolver result
 * @param {import('@aws-appsync/utils').Context} ctx the context
 * @returns {*} the result
 */
export function response(ctx) {
    return ctx.result ? util.dynamodb.toMap(ctx.result) : null;
}